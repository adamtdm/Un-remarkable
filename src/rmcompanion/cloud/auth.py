"""Authentication with reMarkable cloud."""

from __future__ import annotations

import base64
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx

from rmcompanion.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass
class AuthTokens:
    device_token: str = ""
    user_token: str = ""
    device_id: str = ""

    @property
    def is_authenticated(self) -> bool:
        return bool(self.device_token)


class AuthManager:
    """Manages cloud tokens, disk persistence, and token refreshing."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.tokens_path: Path = self.settings.tokens_file
        self.tokens = self._load_tokens()

    def _load_tokens(self) -> AuthTokens:
        if not self.tokens_path.exists():
            return AuthTokens(device_id=str(uuid.uuid4()))
        try:
            with open(self.tokens_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return AuthTokens(
                device_token=data.get("device_token", ""),
                user_token=data.get("user_token", ""),
                device_id=data.get("device_id") or str(uuid.uuid4()),
            )
        except Exception as e:
            logger.warning("Failed to read tokens from %s: %s", self.tokens_path, e)
            return AuthTokens(device_id=str(uuid.uuid4()))

    def save_tokens(self) -> None:
        self.settings.secrets_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "device_token": self.tokens.device_token,
            "user_token": self.tokens.user_token,
            "device_id": self.tokens.device_id,
        }
        tmp_path = self.tokens_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        try:
            os.chmod(tmp_path, 0o600)
        except OSError:
            pass
        tmp_path.replace(self.tokens_path)
        logger.debug("Saved auth tokens to %s", self.tokens_path)

    def clear_tokens(self) -> None:
        """Clear tokens and unlink the device."""
        self.tokens.device_token = ""
        self.tokens.user_token = ""
        if self.tokens_path.exists():
            try:
                self.tokens_path.unlink()
            except OSError as e:
                logger.warning("Failed to delete tokens file %s: %s", self.tokens_path, e)
        logger.info("Unlinked device and cleared auth tokens")

    def is_user_token_valid(self) -> bool:
        """Check if user token is present and not expired."""
        if not self.tokens.user_token:
            return False
        try:
            parts = self.tokens.user_token.split(".")
            if len(parts) < 2:
                # Non-JWT format (or test token), consider valid if non-empty
                return True
            payload = parts[1]
            # Add base64 padding
            padded = payload + "=" * (-len(payload) % 4)
            claims = json.loads(base64.urlsafe_b64decode(padded))
            exp = claims.get("exp")
            if not exp:
                return True
            # Consider expired if within 120 seconds of expiration
            return time.time() < (exp - 120)
        except Exception:
            # If payload cannot be parsed as JSON, treat as valid token string
            return True

    async def register_device(self, one_time_code: str, client: httpx.AsyncClient | None = None) -> str:
        """Exchange an 8-character code from my.remarkable.com for a device token."""
        code = one_time_code.strip().lower()
        if len(code) != 8:
            raise ValueError("One-time code must be exactly 8 characters long")

        if not self.tokens.device_id:
            self.tokens.device_id = str(uuid.uuid4())

        url = f"{self.settings.rm_auth_host}/token/json/2/device/new"
        payload = {
            "code": code,
            "deviceDesc": self.settings.rm_device_desc,
            "deviceID": self.tokens.device_id,
        }

        async def _do_register(c: httpx.AsyncClient) -> str:
            resp = await c.post(url, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(
                    f"Device registration failed ({resp.status_code}): {resp.text}"
                )
            device_token = resp.text.strip()
            if not device_token:
                raise RuntimeError("Empty device token received from cloud")
            self.tokens.device_token = device_token
            await self.refresh_user_token(c)
            self.save_tokens()
            logger.info("Successfully registered device with reMarkable cloud")
            return device_token

        if client:
            return await _do_register(client)
        else:
            async with httpx.AsyncClient(timeout=15.0) as c:
                return await _do_register(c)

    async def refresh_user_token(self, client: httpx.AsyncClient | None = None) -> str:
        """Obtain a new short-lived user token using the device token."""
        if not self.tokens.device_token:
            raise RuntimeError("No device token available. Register device first.")

        url = f"{self.settings.rm_auth_host}/token/json/2/user/new"
        headers = {"Authorization": f"Bearer {self.tokens.device_token}"}

        async def _do_post(c: httpx.AsyncClient) -> str:
            resp = await c.post(url, headers=headers)
            if resp.status_code == 401:
                # Device token has been revoked
                self.tokens.device_token = ""
                self.tokens.user_token = ""
                self.save_tokens()
                raise RuntimeError(
                    "Device token was rejected (401). Re-authentication required."
                )
            if resp.status_code != 200:
                raise RuntimeError(
                    f"User token refresh failed ({resp.status_code}): {resp.text}"
                )
            user_token = resp.text.strip()
            if not user_token:
                raise RuntimeError("Empty user token received from cloud")
            return user_token

        if client:
            user_token = await _do_post(client)
        else:
            async with httpx.AsyncClient(timeout=15.0) as c:
                user_token = await _do_post(c)

        self.tokens.user_token = user_token
        self.save_tokens()
        logger.debug("Successfully refreshed reMarkable cloud user token")
        return user_token

    async def get_valid_user_token(self, client: httpx.AsyncClient | None = None) -> str:
        """Return a valid user token, refreshing if necessary."""
        if not self.is_user_token_valid():
            return await self.refresh_user_token(client)
        return self.tokens.user_token
