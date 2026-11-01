"""Sync engine orchestrating background synchronization with reMarkable cloud."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections.abc import Callable
from typing import Any

from rmcompanion.cloud.auth import AuthManager
from rmcompanion.cloud.client import RMCloudClient
from rmcompanion.cloud.index import Entry, compute_doc_index_hash, compute_root_hash, format_index
from rmcompanion.config import Settings, get_settings
from rmcompanion.render.exporter import Exporter
from rmcompanion.store.blob_store import BlobStore
from rmcompanion.store.db import Database

logger = logging.getLogger(__name__)


class SyncEngine:
    """Synchronizes the local blob store and SQLite database with reMarkable cloud."""

    def __init__(
        self,
        client: RMCloudClient | None = None,
        db: Database | None = None,
        blob_store: BlobStore | None = None,
        auth: AuthManager | None = None,
        settings: Settings | None = None,
        on_doc_indexed: Callable[[str, str], None] | None = None,
        exporter: Exporter | None = None,
        delivery_manager: Any = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.auth = auth or AuthManager(self.settings)
        self.client = client or RMCloudClient(auth=self.auth, settings=self.settings)
        self.db = db or Database(settings=self.settings)
        self.blob_store = blob_store or BlobStore(settings=self.settings)
        self.on_doc_indexed = on_doc_indexed
        self.exporter = exporter or Exporter(db=self.db, blob_store=self.blob_store, settings=self.settings)
        self.delivery_manager = delivery_manager

        self._task: asyncio.Task[None] | None = None
        self._running = False
        self._sync_lock = asyncio.Lock()
        self._progress: dict[str, Any] = {
            "is_syncing": False,
            "stage": "idle",
            "total_docs": 0,
            "current_doc_idx": 0,
            "current_doc_name": "",
            "current_doc_id": "",
            "current_file": "",
            "docs_updated": 0,
            "bytes_downloaded": 0,
            "started_at": 0.0,
            "recent_activity": [],
        }

    def _add_recent_activity(self, item: dict[str, Any]) -> None:
        activity = self._progress["recent_activity"]
        activity.insert(0, item)
        if len(activity) > 30:
            activity.pop()

    @property
    def status(self) -> dict[str, Any]:
        return {
            "status": self.db.get_state("sync_status", "idle"),
            "last_sync_time": float(self.db.get_state("last_sync_time", "0")),
            "last_generation": int(self.db.get_state("last_generation", "0")),
            "last_root_hash": self.db.get_state("last_root_hash", ""),
            "last_error": self.db.get_state("sync_error", ""),
            "is_authenticated": self.auth.tokens.is_authenticated,
            "progress": dict(self._progress),
        }

    async def sync_once(self) -> dict[str, Any]:
        """Perform a single sync cycle."""
        if not self.auth.tokens.is_authenticated:
            self.db.set_state("sync_status", "unauthenticated")
            return {"status": "unauthenticated"}

        if self._sync_lock.locked():
            logger.debug("Sync already in progress; skipping trigger")
            return {"status": "in_progress"}

        async with self._sync_lock:
            self.db.set_state("sync_status", "syncing")
            self.db.set_state("sync_error", "")
            self._progress["is_syncing"] = True
            self._progress["stage"] = "checking_cloud"
            self._progress["started_at"] = time.time()
            self._progress["current_doc_idx"] = 0
            self._progress["docs_updated"] = 0
            start_time = time.time()
            try:
                root_hash, generation, schema_version = await self.client.get_root()
                last_root = self.db.get_state("last_root_hash", "")

                if root_hash == last_root:
                    logger.debug("Remote root hash unchanged (%s, gen %d)", root_hash, generation)
                    self.db.set_state("sync_status", "idle")
                    self.db.set_state("last_sync_time", str(time.time()))
                    self._progress["is_syncing"] = False
                    self._progress["stage"] = "idle"
                    return {
                        "status": "idle",
                        "changed": False,
                        "generation": generation,
                        "root_hash": root_hash,
                        "duration_s": time.time() - start_time,
                    }

                logger.info(
                    "Remote root changed: %s -> %s (generation %d)",
                    last_root[:12] if last_root else "empty",
                    root_hash[:12],
                    generation,
                )

                # Download and save root index
                self._progress["stage"] = "fetching_root"
                root_entries, _, root_raw = await self.client.get_root_index(root_hash)
                self.blob_store.put(root_hash, root_raw, verify=True)

                doc_tuples: list[tuple[str, str]] = []
                updated_count = 0
                self._progress["stage"] = "syncing_documents"
                self._progress["total_docs"] = len(root_entries)

                for idx, entry in enumerate(root_entries):
                    doc_id = entry.doc_id
                    doc_hash = entry.hash
                    doc_tuples.append((doc_id, doc_hash))

                    self._progress["current_doc_idx"] = idx + 1
                    self._progress["current_doc_id"] = doc_id
                    existing_doc = self.db.get_document(doc_id)
                    doc_name = existing_doc.get("visible_name", doc_id) if existing_doc else doc_id
                    self._progress["current_doc_name"] = doc_name

                    # Check if document has been modified
                    if existing_doc and existing_doc.get("doc_hash") == doc_hash:
                        continue

                    await self._sync_document(doc_id, doc_hash, name_hint=doc_name)
                    updated_count += 1
                    self._progress["docs_updated"] = updated_count

                # Record overall snapshot
                self.db.record_snapshot(root_hash, generation, schema_version, doc_tuples)
                self.db.set_state("last_root_hash", root_hash)
                self.db.set_state("last_generation", str(generation))
                self.db.set_state("last_sync_time", str(time.time()))
                self.db.set_state("sync_status", "idle")
                self._progress["is_syncing"] = False
                self._progress["stage"] = "idle"
                self._progress["current_file"] = ""
                self._progress["current_doc_name"] = ""

                logger.info(
                    "Sync complete in %.2fs: %d documents in cloud, %d updated",
                    time.time() - start_time,
                    len(doc_tuples),
                    updated_count,
                )

                return {
                    "status": "idle",
                    "changed": True,
                    "generation": generation,
                    "root_hash": root_hash,
                    "total_docs": len(doc_tuples),
                    "updated_docs": updated_count,
                    "duration_s": time.time() - start_time,
                }

            except Exception as e:
                err_msg = f"Sync failed: {e}"
                logger.exception(err_msg)
                self.db.set_state("sync_status", "error")
                self.db.set_state("sync_error", str(e))
                self._progress["is_syncing"] = False
                self._progress["stage"] = "error"
                return {"status": "error", "error": str(e)}

    async def _sync_document(self, doc_id: str, doc_hash: str, name_hint: str = "") -> None:
        """Fetch index and all subfiles for a single document."""
        logger.debug("Syncing document %s (hash %s)", doc_id, doc_hash[:12])
        file_entries, _, doc_index_raw = await self.client.get_doc_index(doc_hash, doc_id)
        # Note: Document schema indexes are addressed by HashEntries (Merkle hash of children)
        self.blob_store.put(doc_hash, doc_index_raw, verify=False)

        files_meta: list[dict[str, Any]] = []
        metadata_content: dict[str, Any] = {}
        content_data: dict[str, Any] = {}

        for f_entry in file_entries:
            file_id = f_entry.doc_id
            blob_hash = f_entry.hash
            blob_size = f_entry.size
            self._progress["current_file"] = f"{name_hint or doc_id} / {file_id}"

            # Download blob if not present locally
            if not self.blob_store.has(blob_hash):
                raw_blob = await self.client.get_blob(blob_hash, filename=file_id)
                self.blob_store.put(blob_hash, raw_blob, verify=True)
                self._progress["bytes_downloaded"] += len(raw_blob)
            else:
                raw_blob = self.blob_store.get(blob_hash)

            files_meta.append({
                "file_id": file_id,
                "blob_hash": blob_hash,
                "file_type": file_id.split(".")[-1] if "." in file_id else "",
                "size": blob_size,
            })

            # Parse metadata
            if file_id.endswith(".metadata"):
                try:
                    metadata_content = json.loads(raw_blob.decode("utf-8"))
                except Exception as e:
                    logger.warning("Failed to parse metadata for %s: %s", doc_id, e)

            # Parse content
            elif file_id.endswith(".content"):
                try:
                    content_data = json.loads(raw_blob.decode("utf-8"))
                except Exception as e:
                    logger.warning("Failed to parse content for %s: %s", doc_id, e)

        # Build document record
        is_collection = metadata_content.get("type") == "CollectionType"
        doc_type = "CollectionType" if is_collection else "DocumentType"
        file_type = content_data.get("fileType", "notebook") if not is_collection else ""
        if not file_type:
            file_type = "notebook" if not is_collection else ""

        # Parse pages
        pages: list[dict[str, Any]] = []
        c_pages_raw = content_data.get("cPages")
        if isinstance(c_pages_raw, dict) and "pages" in c_pages_raw:
            # Modern firmware 3.0+ cPages format
            c_pages = c_pages_raw["pages"]
            # Sort pages by idx.value if available
            def _get_page_sort_key(p: dict[str, Any]) -> str:
                idx_val = p.get("idx", {})
                if isinstance(idx_val, dict):
                    return str(idx_val.get("value", ""))
                return str(idx_val)

            sorted_c_pages = sorted(c_pages, key=_get_page_sort_key)
            for idx, p in enumerate(sorted_c_pages):
                deleted_val = p.get("deleted", {})
                is_deleted = False
                if isinstance(deleted_val, dict):
                    is_deleted = bool(deleted_val.get("value", 0))
                elif isinstance(deleted_val, (int, bool)):
                    is_deleted = bool(deleted_val)

                redir_val = p.get("redir", {})
                redir_idx = -1
                if isinstance(redir_val, dict):
                    redir_idx = int(redir_val.get("value", -1))
                elif isinstance(redir_val, int):
                    redir_idx = redir_val

                pages.append({
                    "page_idx": idx,
                    "page_id": p.get("id", ""),
                    "deleted": is_deleted,
                    "redir": redir_idx,
                })
        else:
            # Legacy pages array
            legacy_pages = content_data.get("pages", [])
            for idx, page_id in enumerate(legacy_pages):
                pages.append({
                    "page_idx": idx,
                    "page_id": page_id,
                    "deleted": False,
                    "redir": -1,
                })

        # Tags
        tags: list[dict[str, Any]] = []
        for t in content_data.get("tags", []):
            if isinstance(t, dict):
                tags.append({
                    "tag": t.get("name", ""),
                    "page_id": "",
                    "timestamp": t.get("timestamp", 0),
                })
        for pt in content_data.get("pageTags", []):
            if isinstance(pt, dict):
                tags.append({
                    "tag": pt.get("name", ""),
                    "page_id": pt.get("pageId", ""),
                    "timestamp": pt.get("timestamp", 0),
                })

        doc_record = {
            "id": doc_id,
            "visible_name": metadata_content.get("visibleName", doc_id),
            "type": doc_type,
            "parent_id": metadata_content.get("parent", ""),
            "last_modified": str(metadata_content.get("lastModified", "")),
            "last_opened": str(metadata_content.get("lastOpened", "")),
            "last_opened_page": int(metadata_content.get("lastOpenedPage", 0)),
            "pinned": bool(metadata_content.get("pinned", False)),
            "deleted": bool(metadata_content.get("deleted", False)),
            "file_type": file_type,
            "page_count": len([p for p in pages if not p["deleted"]]),
            "doc_hash": doc_hash,
        }

        self.db.upsert_document(doc_record)
        self.db.set_document_files(doc_hash, files_meta)
        self.db.set_document_pages(doc_hash, pages)
        self.db.set_document_tags(doc_id, tags)

        self._add_recent_activity({
            "timestamp": time.time(),
            "doc_id": doc_id,
            "name": doc_record["visible_name"],
            "type": doc_record["file_type"] or doc_record["type"],
            "pages": doc_record["page_count"],
            "status": "synced",
        })

        if doc_record["type"] != "CollectionType" and not doc_record["deleted"]:
            try:
                self.exporter.warm_thumbnail(doc_id, doc_hash)
            except Exception as e:
                logger.debug("Failed to warm thumbnail for %s: %s", doc_id, e)

        if self.on_doc_indexed and not doc_record["deleted"]:
            try:
                self.on_doc_indexed(doc_id, doc_hash)
            except Exception as e:
                logger.warning("Error running on_doc_indexed callback for %s: %s", doc_id, e)

    async def push_document(
        self,
        file_bytes: bytes,
        filename: str,
        parent_id: str = "",
        file_type: str = "pdf",
    ) -> dict[str, Any]:
        """Upload a PDF or EPUB document to reMarkable Cloud and trigger sync."""
        if not self.auth.tokens.is_authenticated:
            return {"status": "unauthenticated"}

        try:
            res = await self.client.upload_document(
                file_bytes=file_bytes,
                filename=filename,
                parent_id=parent_id or "",
                file_type=file_type,
            )
            # Schedule immediate sync cycle to ingest the new cloud document
            asyncio.create_task(self.sync_once())
            return {"status": "ok", "result": res}
        except Exception as e:
            logger.error("Failed to push document %s to reMarkable Cloud: %s", filename, e)
            return {"status": "error", "error": str(e)}

    async def create_remote_folder(self, folder_id: str, name: str, parent_id: str = "") -> bool:
        """Create a collection folder on reMarkable Cloud and broadcast update."""
        if not self.auth.tokens.is_authenticated:
            return False

        try:
            now_ms = str(int(time.time() * 1000))
            meta_dict = {
                "createdTime": now_ms,
                "lastModified": now_ms,
                "new": True,
                "parent": parent_id or "",
                "pinned": False,
                "source": "",
                "type": "CollectionType",
                "visibleName": name,
            }
            meta_bytes = json.dumps(meta_dict, indent=2).encode("utf-8")
            meta_hash = hashlib.sha256(meta_bytes).hexdigest()

            meta_entry = Entry(
                hash=meta_hash,
                type="0",
                doc_id=f"{folder_id}.metadata",
                subfiles=0,
                size=len(meta_bytes),
            )
            folder_doc_hash = compute_doc_index_hash([meta_entry])
            doc_schema_bytes = format_index([meta_entry], schema="3").encode("utf-8")

            # 1. Upload metadata blob
            await self.client.put_blob(meta_hash, meta_bytes, f"{folder_id}.metadata")

            # 2. Upload docSchema blob
            await self.client.put_blob(
                folder_doc_hash,
                doc_schema_bytes,
                f"{folder_id}.docSchema",
                content_type="text/plain; charset=UTF-8",
            )

            # 3. Add to cloud root index and broadcast
            root_hash, gen, schema = await self.client.get_root()
            entries, _, _ = await self.client.get_root_index(root_hash)
            folder_entry = Entry(
                hash=folder_doc_hash,
                type="0",
                doc_id=folder_id,
                subfiles=1,
                size=len(meta_bytes),
            )
            entries.append(folder_entry)

            new_root_bytes = format_index(entries, schema=schema).encode("utf-8")
            new_root_hash = compute_root_hash(new_root_bytes)
            await self.client.put_blob(
                new_root_hash,
                new_root_bytes,
                "root.docSchema",
                content_type="text/plain; charset=UTF-8",
            )

            new_gen = await self.client.update_root(new_root_hash, gen, broadcast=True)
            self.db.set_state("last_root_hash", new_root_hash)
            self.db.set_state("last_generation", str(new_gen))
            logger.info("Created folder %s (%s) on reMarkable Cloud", name, folder_id)
            return True
        except Exception as e:
            logger.warning("Failed to create remote folder %s on cloud: %s", name, e)
            return False

    async def move_remote_document(self, doc_id: str, new_parent_id: str = "") -> bool:
        """Update parent ID for a document or folder on reMarkable Cloud and broadcast."""
        if not self.auth.tokens.is_authenticated:
            return False

        try:
            root_hash, gen, schema = await self.client.get_root()
            entries, _, _ = await self.client.get_root_index(root_hash)

            doc_entry = next((e for e in entries if e.doc_id == doc_id), None)
            if not doc_entry:
                logger.debug("Document %s not found in cloud root; skipping remote move", doc_id)
                return False

            doc_entries, doc_schema_ver, _ = await self.client.get_doc_index(doc_entry.hash, doc_id)
            meta_entry = next((e for e in doc_entries if e.doc_id.endswith(".metadata")), None)
            if not meta_entry:
                return False

            # Download existing metadata blob
            raw_meta = await self.client.get_blob(meta_entry.hash, meta_entry.doc_id)
            meta_dict = json.loads(raw_meta.decode("utf-8"))
            meta_dict["parent"] = new_parent_id or ""
            meta_dict["lastModified"] = str(int(time.time() * 1000))
            new_meta_bytes = json.dumps(meta_dict, indent=2).encode("utf-8")
            new_meta_hash = hashlib.sha256(new_meta_bytes).hexdigest()

            # Upload updated metadata blob
            await self.client.put_blob(new_meta_hash, new_meta_bytes, meta_entry.doc_id)

            # Recompute doc index
            updated_doc_entries = [
                Entry(hash=new_meta_hash, type=e.type, doc_id=e.doc_id, subfiles=e.subfiles, size=len(new_meta_bytes))
                if e.doc_id == meta_entry.doc_id else e
                for e in doc_entries
            ]
            new_doc_hash = compute_doc_index_hash(updated_doc_entries)
            doc_schema_bytes = format_index(updated_doc_entries, schema=doc_schema_ver).encode("utf-8")
            await self.client.put_blob(
                new_doc_hash,
                doc_schema_bytes,
                f"{doc_id}.docSchema",
                content_type="text/plain; charset=UTF-8",
            )

            # Update root index
            updated_root_entries = [
                Entry(hash=new_doc_hash, type=e.type, doc_id=e.doc_id, subfiles=e.subfiles, size=e.size)
                if e.doc_id == doc_id else e
                for e in entries
            ]
            new_root_bytes = format_index(updated_root_entries, schema=schema).encode("utf-8")
            new_root_hash = compute_root_hash(new_root_bytes)
            await self.client.put_blob(
                new_root_hash,
                new_root_bytes,
                "root.docSchema",
                content_type="text/plain; charset=UTF-8",
            )

            new_gen = await self.client.update_root(new_root_hash, gen, broadcast=True)
            self.db.set_state("last_root_hash", new_root_hash)
            self.db.set_state("last_generation", str(new_gen))
            logger.info("Moved document %s to parent '%s' on reMarkable Cloud", doc_id, new_parent_id)
            return True
        except Exception as e:
            logger.warning("Failed to move remote document %s on cloud: %s", doc_id, e)
            return False

    async def delete_remote_document(self, doc_id: str) -> bool:
        """Remove document or folder from reMarkable Cloud root index and broadcast."""
        if not self.auth.tokens.is_authenticated:
            return False

        try:
            root_hash, gen, schema = await self.client.get_root()
            entries, _, _ = await self.client.get_root_index(root_hash)

            filtered = [e for e in entries if e.doc_id != doc_id]
            if len(filtered) == len(entries):
                return True

            new_root_bytes = format_index(filtered, schema=schema).encode("utf-8")
            new_root_hash = compute_root_hash(new_root_bytes)
            await self.client.put_blob(
                new_root_hash,
                new_root_bytes,
                "root.docSchema",
                content_type="text/plain; charset=UTF-8",
            )

            new_gen = await self.client.update_root(new_root_hash, gen, broadcast=True)
            self.db.set_state("last_root_hash", new_root_hash)
            self.db.set_state("last_generation", str(new_gen))
            logger.info("Deleted document %s from reMarkable Cloud", doc_id)
            return True
        except Exception as e:
            logger.warning("Failed to delete remote document %s on cloud: %s", doc_id, e)
            return False

    def start_background_loop(self) -> None:
        """Start recurring background sync task."""
        if self._running:
            return
        self._running = True

        async def _loop() -> None:
            logger.info(
                "Starting background sync loop (every %ds)",
                self.settings.sync_interval_seconds,
            )
            while self._running:
                try:
                    await self.sync_once()
                    if self.delivery_manager:
                        try:
                            await self.delivery_manager.check_scheduled_delivery()
                        except Exception as de:
                            logger.error("Error checking scheduled delivery: %s", de)
                except Exception as e:
                    logger.error("Unexpected error in background sync loop: %s", e)
                await asyncio.sleep(self.settings.sync_interval_seconds)

        self._task = asyncio.create_task(_loop())

    def trigger(self) -> None:
        """Trigger an immediate background sync pass if not already syncing."""
        if not self._progress.get("is_syncing", False):
            asyncio.create_task(self.sync_once())

    def stop(self) -> None:
        """Stop background sync loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("Background sync loop stopped")
