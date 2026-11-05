"""Vision and OCR provider client supporting Google Gemini and OpenAI/Ollama."""

from __future__ import annotations

import base64
import json
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class VisionProvider:
    """Dispatches vision and handwriting extraction prompts to cloud or local models."""

    def __init__(
        self,
        provider: str = "gemini",
        api_key: str = "",
        model: str = "gemini-flash-lite-latest",
        base_url: str = "",
    ) -> None:
        self.provider = provider.lower()
        self.api_key = api_key.strip()
        default_m = "gemini-flash-lite-latest" if self.provider == "gemini" else "gpt-4o-mini"
        self.model = model.strip() or default_m
        self.base_url = base_url.rstrip("/")

    async def analyze_image(
        self,
        image_bytes: bytes,
        prompt: str,
        system_prompt: str = "",
        timeout: float = 45.0,
    ) -> str:
        """Send image and prompt to configured model and return text response."""
        if self.provider == "gemini":
            return await self._call_gemini(image_bytes, prompt, system_prompt, timeout)
        else:
            return await self._call_openai_compatible(image_bytes, prompt, system_prompt, timeout)

    async def _call_gemini(
        self,
        image_bytes: bytes,
        prompt: str,
        system_prompt: str,
        timeout: float,
    ) -> str:
        if not self.api_key:
            raise ValueError("Gemini API key is required")

        model_clean = self.model.strip().removeprefix("models/")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_clean}:generateContent"
        headers = {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        params = {"key": self.api_key}

        parts: list[dict[str, Any]] = [
            {"text": f"{system_prompt}\n\n{prompt}" if system_prompt else prompt}
        ]
        if image_bytes:
            b64_image = base64.b64encode(image_bytes).decode("ascii")
            parts.append({
                "inline_data": {
                    "mime_type": "image/png",
                    "data": b64_image,
                }
            })

        payload = {"contents": [{"parts": parts}]}

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers, params=params, json=payload)
            if resp.status_code != 200:
                err_detail = resp.text
                try:
                    err_json = resp.json()
                    err_detail = err_json.get("error", {}).get("message", err_detail)
                except Exception:
                    pass
                raise RuntimeError(f"Gemini API error ({resp.status_code}): {err_detail}")

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return ""
            parts = candidates[0].get("content", {}).get("parts", [])
            return "".join(p.get("text", "") for p in parts).strip()

    async def _call_openai_compatible(
        self,
        image_bytes: bytes,
        prompt: str,
        system_prompt: str,
        timeout: float,
    ) -> str:
        base = self.base_url or "https://api.openai.com"
        url = f"{base}/v1/chat/completions"
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        user_content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        if image_bytes:
            b64_image = base64.b64encode(image_bytes).decode("ascii")
            data_url = f"data:image/png;base64,{b64_image}"
            user_content.append({"type": "image_url", "image_url": {"url": data_url}})

        messages.append({
            "role": "user",
            "content": user_content,
        })

        payload = {
            "model": self.model,
            "messages": messages,
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Vision API error ({resp.status_code}): {resp.text}")
            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                return ""
            return choices[0].get("message", {}).get("content", "").strip()

    async def test_connection(self) -> dict[str, Any]:
        """Test the provider configuration with a minimal ping prompt."""
        t0 = time.time()
        if self.provider == "gemini":
            if not self.api_key:
                raise ValueError("Gemini API key is required")
            model_clean = self.model.strip().removeprefix("models/")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_clean}:generateContent"
            headers = {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}
            params = {"key": self.api_key}
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": "Respond with only the single word: OK"}
                        ]
                    }
                ]
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, headers=headers, params=params, json=payload)
                if resp.status_code != 200:
                    err_msg = resp.text
                    try:
                        err_msg = resp.json().get("error", {}).get("message", err_msg)
                    except Exception:
                        pass
                    raise RuntimeError(f"Gemini API error ({resp.status_code}): {err_msg}")
                data = resp.json()
                candidates = data.get("candidates", [])
                text = ""
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    text = "".join(p.get("text", "") for p in parts).strip()
                latency = round(time.time() - t0, 3)
                return {
                    "ok": True,
                    "provider": self.provider,
                    "model": self.model,
                    "latency_s": latency,
                    "reply": text or "OK",
                }
        else:
            base = self.base_url or "https://api.openai.com"
            url = f"{base}/v1/chat/completions"
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": "Respond with only the single word: OK"}],
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    raise RuntimeError(f"Vision API error ({resp.status_code}): {resp.text}")
                data = resp.json()
                choices = data.get("choices", [])
                text = ""
                if choices:
                    text = choices[0].get("message", {}).get("content", "").strip()
                latency = round(time.time() - t0, 3)
                return {
                    "ok": True,
                    "provider": self.provider,
                    "model": self.model,
                    "latency_s": latency,
                    "reply": text or "OK",
                }


def get_effective_vision_config(db: Any = None, settings: Any = None) -> dict[str, Any]:
    """Resolve effective vision config merging database state and container settings/environment."""
    from rmcompanion.config import get_settings
    app_settings = settings or get_settings()

    db_conf: dict[str, Any] = {}
    if db is not None:
        try:
            raw = db.get_state("vision_settings", "")
            if raw:
                db_conf = json.loads(raw)
        except Exception as e:
            logger.warning("Failed reading vision_settings from DB: %s", e)

    provider = (db_conf.get("provider") or app_settings.vision_provider or "gemini").lower()

    # Resolve API key
    db_key = ""
    if db_conf.get("provider") == provider:
        db_key = db_conf.get("api_key", "").strip()
    elif not db_conf.get("provider"):
        db_key = db_conf.get("api_key", "").strip()

    if db_key:
        api_key = db_key
        api_key_source = "database"
    elif provider == "gemini" and app_settings.gemini_api_key:
        api_key = app_settings.gemini_api_key.strip()
        api_key_source = "environment"
    elif provider in ("openai", "ollama") and app_settings.openai_api_key:
        api_key = app_settings.openai_api_key.strip()
        api_key_source = "environment"
    else:
        api_key = ""
        api_key_source = "none"

    # Resolve Base URL
    base_url = db_conf.get("base_url", "").strip() or app_settings.openai_base_url.strip()
    if not base_url and provider == "ollama":
        base_url = "http://localhost:11434"

    # Resolve Model
    default_model = "gemini-flash-lite-latest" if provider == "gemini" else "gpt-4o-mini"
    model = db_conf.get("model", "").strip() or app_settings.vision_model.strip() or default_model

    return {
        "provider": provider,
        "api_key": api_key,
        "api_key_source": api_key_source,
        "model": model,
        "base_url": base_url,
    }


def get_vision_provider(db: Any = None, settings: Any = None) -> VisionProvider | None:
    """Load vision provider from database app state with container environment fallback."""
    try:
        conf = get_effective_vision_config(db, settings)
        provider = conf["provider"]
        api_key = conf["api_key"]

        # Ollama local models do not require an API key
        if not api_key and provider not in ("ollama", "local"):
            return None

        return VisionProvider(
            provider=provider,
            api_key=api_key,
            model=conf["model"],
            base_url=conf["base_url"],
        )
    except Exception as e:
        logger.warning("Failed to initialize vision provider: %s", e)
        return None
