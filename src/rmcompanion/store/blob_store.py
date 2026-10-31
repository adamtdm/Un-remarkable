"""Content-addressed filesystem blob store for immutable reMarkable files."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from rmcompanion.config import Settings, get_settings

logger = logging.getLogger(__name__)


class BlobStore:
    """Stores files on disk indexed by their SHA-256 hash.

    Blobs are immutable and content-verified. Once written, they are never deleted,
    allowing full snapshot and version history retention.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base_dir: Path = self.settings.blobs_dir

    def _blob_path(self, blob_hash: str) -> Path:
        h = blob_hash.lower()
        if len(h) < 4:
            return self.base_dir / h
        return self.base_dir / h[:2] / h[2:4] / h

    def has(self, blob_hash: str) -> bool:
        return self._blob_path(blob_hash).is_file()

    def get_path(self, blob_hash: str) -> Path | None:
        p = self._blob_path(blob_hash)
        return p if p.is_file() else None

    def get(self, blob_hash: str) -> bytes:
        p = self._blob_path(blob_hash)
        if not p.is_file():
            raise FileNotFoundError(f"Blob not found in store: {blob_hash}")
        return p.read_bytes()

    def put(self, blob_hash: str, data: bytes, verify: bool = True) -> Path:
        """Write blob to store. Returns final path."""
        h = blob_hash.lower()
        if verify:
            computed = hashlib.sha256(data).hexdigest()
            if computed != h:
                raise ValueError(
                    f"Blob content hash mismatch: expected {h}, computed {computed}"
                )

        target_path = self._blob_path(h)
        if target_path.is_file():
            # Already exists in content-addressed store
            return target_path

        target_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target_path.with_suffix(".tmp")
        tmp_path.write_bytes(data)
        tmp_path.replace(target_path)
        return target_path

    def stats(self) -> tuple[int, int]:
        """Return (blob_count, total_bytes)."""
        count = 0
        total_size = 0
        for p in self.base_dir.rglob("*"):
            if p.is_file() and not p.name.endswith(".tmp"):
                count += 1
                total_size += p.stat().st_size
        return count, total_size
