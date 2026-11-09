"""End-to-end sync engine tests using an in-memory mock reMarkable cloud."""

import hashlib
import json
from pathlib import Path

import httpx
import pytest

from rmcompanion.cloud.auth import AuthManager, AuthTokens
from rmcompanion.cloud.client import RMCloudClient
from rmcompanion.cloud.index import (
    Entry,
    compute_doc_index_hash,
    compute_root_hash,
    format_index,
)
from rmcompanion.config import Settings
from rmcompanion.index.text_indexer import TextIndexer
from rmcompanion.store.blob_store import BlobStore
from rmcompanion.store.db import Database
from rmcompanion.sync.engine import SyncEngine

SAMPLE_RM = Path(__file__).parent / "fixtures" / "rm" / "Bold_Heading_Bullet_Normal.rm"


class MockCloudTransport(httpx.AsyncBaseTransport):
    """Mock HTTP transport returning realistic reMarkable sync responses."""

    def __init__(self):
        self.blobs: dict[str, bytes] = {}
        self.root_hash = ""
        self.generation = 1
        self.schema_version = "4"

    def put_blob(self, data: bytes) -> str:
        h = hashlib.sha256(data).hexdigest()
        self.blobs[h] = data
        return h

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)

        # 1. Root index endpoint
        if "/sync/v4/root" in url_str:
            return httpx.Response(
                200,
                json={
                    "hash": self.root_hash,
                    "generation": self.generation,
                    "schemaVersion": int(self.schema_version),
                },
            )

        # Uploads: blobs and root updates (used by push_local_notebook)
        if request.method == "PUT" and "/sync/v3/files/" in url_str:
            self.put_blob(request.content)
            return httpx.Response(200)
        if request.method == "PUT" and "/sync/v3/root" in url_str:
            body = json.loads(request.content)
            self.root_hash = body["hash"]
            self.generation += 1
            return httpx.Response(200, json={"generation": self.generation})

        # 2. File blob download endpoint
        if "/sync/v3/files/" in url_str:
            blob_hash = url_str.split("/sync/v3/files/")[-1].split("?")[0]
            if blob_hash in self.blobs:
                return httpx.Response(200, content=self.blobs[blob_hash])
            return httpx.Response(404, text=f"Blob {blob_hash} not found")

        # 3. User token endpoint
        if "/token/json/2/user/new" in url_str:
            return httpx.Response(200, text="mock_user_token.payload.signature")

        return httpx.Response(404, text="Unknown mock endpoint")


@pytest.fixture
def mock_cloud():
    cloud = MockCloudTransport()

    # Create a test document
    doc_id = "test-doc-uuid"

    metadata_bytes = json.dumps({
        "visibleName": "Quarterly Plan",
        "type": "DocumentType",
        "parent": "",
        "lastModified": "1730000000000",
        "pinned": True,
    }).encode("utf-8")
    meta_hash = cloud.put_blob(metadata_bytes)

    rm_bytes = SAMPLE_RM.read_bytes() if SAMPLE_RM.exists() else b"\x00" * 32
    rm_hash = cloud.put_blob(rm_bytes)

    content_bytes = json.dumps({
        "fileType": "notebook",
        "cPages": {
            "pages": [{"id": "page-1", "idx": {"value": "0001"}}]
        },
    }).encode("utf-8")
    content_hash = cloud.put_blob(content_bytes)

    # Document index entries (schema 3)
    doc_entries = [
        Entry(hash=content_hash, type="0", doc_id=f"{doc_id}.content", subfiles=0, size=len(content_bytes)),
        Entry(hash=meta_hash, type="0", doc_id=f"{doc_id}.metadata", subfiles=0, size=len(metadata_bytes)),
        Entry(hash=rm_hash, type="0", doc_id=f"{doc_id}/page-1.rm", subfiles=0, size=len(rm_bytes)),
    ]
    doc_index_text = format_index(doc_entries, schema="3")
    doc_index_hash = compute_doc_index_hash(doc_entries)
    cloud.blobs[doc_index_hash] = doc_index_text.encode("utf-8")

    # Root index entries (schema 4)
    root_entries = [
        Entry(hash=doc_index_hash, type="80000000", doc_id=doc_id, subfiles=1, size=len(doc_index_text)),
    ]
    root_text = format_index(root_entries, schema="4")
    root_hash = compute_root_hash(root_text)
    cloud.blobs[root_hash] = root_text.encode("utf-8")
    cloud.root_hash = root_hash

    return cloud


@pytest.mark.asyncio
async def test_full_sync_cycle(tmp_path, mock_cloud):
    settings = Settings(data_dir=tmp_path)
    db = Database(settings=settings)
    blob_store = BlobStore(settings=settings)

    # Pre-configure auth tokens
    auth = AuthManager(settings=settings)
    auth.tokens = AuthTokens(device_token="mock_dev_token", user_token="mock_user_token")

    http_client = httpx.AsyncClient(transport=mock_cloud)
    client = RMCloudClient(auth=auth, settings=settings, http_client=http_client)
    text_indexer = TextIndexer(db=db, blob_store=blob_store)

    engine = SyncEngine(
        client=client,
        db=db,
        blob_store=blob_store,
        auth=auth,
        settings=settings,
        on_doc_indexed=text_indexer.index_document,
    )

    # 1. Initial Sync
    res1 = await engine.sync_once()
    assert res1["status"] == "idle"
    assert res1["changed"] is True
    assert res1["total_docs"] == 1
    assert res1["updated_docs"] == 1

    # Verify DB state
    doc = db.get_document("test-doc-uuid")
    assert doc is not None
    assert doc["visible_name"] == "Quarterly Plan"
    assert doc["pinned"] is True
    assert len(doc["pages"]) == 1
    assert len(doc["files"]) == 3

    # Verify Search Indexing
    search_res = db.search("alphabet")
    if SAMPLE_RM.exists():
        assert len(search_res) >= 1
        assert search_res[0]["doc_id"] == "test-doc-uuid"

    # 2. Subsequent sync without changes should be immediate
    res2 = await engine.sync_once()
    assert res2["status"] == "idle"
    assert res2["changed"] is False

    await http_client.aclose()


@pytest.mark.asyncio
async def test_tasks_notebook_updates_in_place_and_changed_pages_reported(tmp_path, mock_cloud):
    """The Tasks notebook must exist once in the cloud, however often it is rebuilt,
    and a sync must report which pages got new handwriting."""
    from rmcompanion.editor.notebook_editor import NotebookEditor

    settings = Settings(data_dir=tmp_path)
    db = Database(settings=settings)
    blob_store = BlobStore(settings=settings)
    auth = AuthManager(settings=settings)
    auth.tokens = AuthTokens(device_token="mock_dev_token", user_token="mock_user_token")
    http_client = httpx.AsyncClient(transport=mock_cloud)
    client = RMCloudClient(auth=auth, settings=settings, http_client=http_client)

    reported: list[dict[str, list[int]]] = []

    async def on_pages_changed(changes: dict[str, list[int]]) -> None:
        reported.append(changes)

    engine = SyncEngine(
        client=client, db=db, blob_store=blob_store, auth=auth, settings=settings,
        on_pages_changed=on_pages_changed,
    )
    await engine.sync_once()
    assert reported == [], "first sync of a library must not trigger a full OCR pass"

    # Push the Tasks notebook twice: one cloud document, updated in place.
    editor = NotebookEditor(db=db, blob_store=blob_store)
    first = editor.append_task_to_tasks_notebook("Book the venue")
    assert await engine.push_local_notebook(first["id"])
    second = editor.append_task_to_tasks_notebook("Send the agenda")
    assert second["id"] == first["id"]
    assert await engine.push_local_notebook(second["id"])

    entries, _, _ = await client.get_root_index(mock_cloud.root_hash)
    assert [e.doc_id for e in entries].count(first["id"]) == 1
    assert len(entries) == 2  # the original document plus Tasks

    # Folders are written in the same v4 index format the tablet uses.
    assert await engine.create_remote_folder("folder-uuid", "Inbox")
    entries, _, _ = await client.get_root_index(mock_cloud.root_hash)
    folder_entry = next(e for e in entries if e.doc_id == "folder-uuid")
    folder_index = mock_cloud.blobs[folder_entry.hash]
    assert folder_index.startswith(b"4\n0:folder-uuid:1:")
    assert hashlib.sha256(folder_index).hexdigest() == folder_entry.hash

    # Change the handwriting on the user's notebook page in the cloud.
    doc_id = "test-doc-uuid"
    root_entries, _, _ = await client.get_root_index(mock_cloud.root_hash)
    doc_entry = next(e for e in root_entries if e.doc_id == doc_id)
    file_entries, _, _ = await client.get_doc_index(doc_entry.hash, doc_id)
    new_rm = b"reMarkable .lines file, version=6" + b"\x00" * 40
    new_rm_hash = mock_cloud.put_blob(new_rm)
    file_entries = [
        Entry(hash=new_rm_hash, type="0", doc_id=e.doc_id, subfiles=0, size=len(new_rm)) if e.doc_id.endswith(".rm") else e
        for e in file_entries
    ]
    doc_index = format_index(file_entries, schema="3")
    new_doc_hash = compute_doc_index_hash(file_entries)
    mock_cloud.blobs[new_doc_hash] = doc_index.encode("utf-8")
    root_entries = [
        Entry(hash=new_doc_hash, type=e.type, doc_id=e.doc_id, subfiles=e.subfiles, size=e.size) if e.doc_id == doc_id else e
        for e in root_entries
    ]
    root_text = format_index(root_entries, schema="4")
    mock_cloud.root_hash = mock_cloud.put_blob(root_text.encode("utf-8"))

    await engine.sync_once()
    for task in list(engine._bg_tasks):
        await task
    changed = {k: v for r in reported for k, v in r.items()}
    assert changed.get(doc_id) == [0]

    await http_client.aclose()
