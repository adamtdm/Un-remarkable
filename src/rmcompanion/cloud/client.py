"""HTTP client for reMarkable sync v3/v4 APIs with concurrency control and retries."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import struct
from typing import Any

import httpx

from rmcompanion.cloud.auth import AuthManager
from rmcompanion.cloud.index import Entry, parse_index
from rmcompanion.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Precomputed Castagnoli CRC32C table (0x82F63B78 polynomial used by Google Cloud Storage)
_CRC32C_TABLE: list[int] = []
for _i in range(256):
    _curr = _i
    for _ in range(8):
        _curr = 0x82F63B78 ^ (_curr >> 1) if (_curr & 1) else (_curr >> 1)
    _CRC32C_TABLE.append(_curr)


def crc32c(data: bytes) -> str:
    """Compute base64-encoded CRC32C checksum for Google Cloud Storage."""
    crc = 0xFFFFFFFF
    for b in data:
        crc = _CRC32C_TABLE[(crc ^ b) & 0xFF] ^ (crc >> 8)
    crc ^= 0xFFFFFFFF
    return base64.b64encode(struct.pack(">I", crc)).decode("ascii")


class RMCloudError(Exception):
    """Base error for reMarkable cloud operations."""


class RMCloudAuthError(RMCloudError):
    """Authentication or token rejection error."""


class RMCloudClient:
    """Async client interacting with reMarkable sync endpoints."""

    def __init__(
        self,
        auth: AuthManager | None = None,
        settings: Settings | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.auth = auth or AuthManager(self.settings)
        self._external_client = http_client
        self._semaphore = asyncio.Semaphore(self.settings.max_concurrent_downloads)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._external_client is not None:
            return self._external_client
        return httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=15.0), follow_redirects=True)

    async def _request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        retry_auth: bool = True,
        retries: int = 3,
        **kwargs: Any,
    ) -> httpx.Response:
        req_headers = {
            "User-Agent": "rmapi/0.0.32-rmcompanion",
        }
        if headers:
            req_headers.update(headers)

        # Acquire token if not provided in headers
        client = await self._get_client()
        attempt = 0
        backoff = 1.0
        try:
            if "Authorization" not in req_headers:
                user_token = await self.auth.get_valid_user_token(client)
                req_headers["Authorization"] = f"Bearer {user_token}"

            while True:
                attempt += 1
                resp = await client.request(method, url, headers=req_headers, follow_redirects=True, **kwargs)

                # Handle token expiry
                if resp.status_code == 401 and retry_auth:
                    logger.info("Received 401 Unauthorized from %s. Refreshing user token...", url)
                    user_token = await self.auth.refresh_user_token(client)
                    req_headers["Authorization"] = f"Bearer {user_token}"
                    return await self._request(
                        method, url, headers=req_headers, retry_auth=False, retries=retries, **kwargs
                    )

                # Handle rate limiting or server errors
                if resp.status_code in (429, 500, 502, 503, 504) and attempt <= retries:
                    logger.warning(
                        "Cloud request %s %s returned status %d. Backing off %.1fs (attempt %d/%d)...",
                        method,
                        url,
                        resp.status_code,
                        backoff,
                        attempt,
                        retries,
                    )
                    await asyncio.sleep(backoff)
                    backoff *= 2.0
                    continue

                return resp
        finally:
            if self._external_client is None:
                await client.aclose()

    async def get_root(self) -> tuple[str, int, str]:
        """Fetch current root hash, generation, and schema version.

        Returns:
            (root_hash, generation, schema_version)
        """
        url = f"{self.settings.rm_sync_host}/sync/v4/root"
        resp = await self._request("GET", url)
        if resp.status_code != 200:
            raise RMCloudError(f"Failed to fetch root index ({resp.status_code}): {resp.text}")

        data = resp.json()
        root_hash = data.get("hash", "")
        generation = int(data.get("generation", 0))
        schema_version = str(data.get("schemaVersion", "4"))
        return root_hash, generation, schema_version

    async def get_blob(self, blob_hash: str, filename: str = "") -> bytes:
        """Download a content blob by SHA-256 hash."""
        url = f"{self.settings.rm_sync_host}/sync/v3/files/{blob_hash}"
        headers = {}
        if filename:
            headers["rm-filename"] = filename

        async with self._semaphore:
            resp = await self._request("GET", url, headers=headers)
            if resp.status_code != 200:
                raise RMCloudError(
                    f"Failed to download blob {blob_hash} ({filename}): status {resp.status_code}"
                )
            return resp.content

    async def get_root_index(self, root_hash: str) -> tuple[list[Entry], str, bytes]:
        """Fetch and parse root index."""
        raw = await self.get_blob(root_hash, filename="root.docSchema")
        entries, schema = parse_index(raw)
        return entries, schema, raw

    async def get_doc_index(self, doc_hash: str, doc_id: str) -> tuple[list[Entry], str, bytes]:
        """Fetch and parse a document's index."""
        raw = await self.get_blob(doc_hash, filename=f"{doc_id}.docSchema")
        entries, schema = parse_index(raw)
        return entries, schema, raw

    async def put_blob(
        self,
        blob_hash: str,
        data: bytes,
        filename: str = "",
        content_type: str = "application/octet-stream",
    ) -> None:
        """Upload a content blob to reMarkable sync storage."""
        url = f"{self.settings.rm_sync_host}/sync/v3/files/{blob_hash}"
        headers = {
            "Content-Type": content_type,
            "x-goog-hash": f"crc32c={crc32c(data)}",
        }
        if filename:
            headers["rm-filename"] = filename

        async with self._semaphore:
            resp = await self._request("PUT", url, headers=headers, content=data)
            if resp.status_code not in (200, 201):
                raise RMCloudError(
                    f"Failed to upload blob {blob_hash} ({filename}): status {resp.status_code} {resp.text}"
                )

    async def update_root(self, root_hash: str, generation: int, broadcast: bool = True) -> int:
        """Update remote root index and broadcast notification to tablets.

        Returns:
            New generation integer.
        """
        url = f"{self.settings.rm_sync_host}/sync/v3/root"
        headers = {
            "rm-filename": "roothash",
            "Content-Type": "application/json",
        }
        payload = {
            "broadcast": broadcast,
            "hash": root_hash,
            "generation": generation,
        }
        resp = await self._request("PUT", url, headers=headers, json=payload)
        if resp.status_code != 200:
            raise RMCloudError(f"Failed to update root index ({resp.status_code}): {resp.text}")

        data = resp.json()
        return int(data.get("generation", generation + 1))

    async def upload_document(
        self,
        file_bytes: bytes,
        filename: str,
        parent_id: str = "",
        file_type: str = "pdf",
    ) -> dict[str, Any]:
        """Upload a PDF or EPUB document directly to reMarkable Cloud.

        Uses the official reMarkable direct document creation API.
        """
        url = f"{self.settings.rm_sync_host}/doc/v2/files"
        meta_dict = {
            "file_name": filename,
            "parent": parent_id or "",
        }
        meta_b64 = base64.b64encode(json.dumps(meta_dict).encode("utf-8")).decode("ascii")
        content_type = "application/epub+zip" if file_type.lower() == "epub" else "application/pdf"
        headers = {
            "rm-source": "WebLibrary",
            "rm-meta": meta_b64,
            "Content-Type": content_type,
        }
        resp = await self._request("POST", url, headers=headers, content=file_bytes)
        if resp.status_code not in (200, 201):
            raise RMCloudError(f"Failed to upload document {filename} ({resp.status_code}): {resp.text}")

        return resp.json()
