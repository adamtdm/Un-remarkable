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

    sample_rm = Path("/home/mcsbot/.gemini/antigravity/brain/fd0749e6-e1d3-47bc-b961-77d3e8b3ec6d/scratch/ref/rmscene/tests/data/Bold_Heading_Bullet_Normal.rm")
    rm_bytes = sample_rm.read_bytes() if sample_rm.exists() else b"\x00" * 32
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
    if Path("/home/mcsbot/.gemini/antigravity/brain/fd0749e6-e1d3-47bc-b961-77d3e8b3ec6d/scratch/ref/rmscene/tests/data/Bold_Heading_Bullet_Normal.rm").exists():
        assert len(search_res) >= 1
        assert search_res[0]["doc_id"] == "test-doc-uuid"

    # 2. Subsequent sync without changes should be immediate
    res2 = await engine.sync_once()
    assert res2["status"] == "idle"
    assert res2["changed"] is False

    await http_client.aclose()
