"""Tests for Model Context Protocol (MCP) server tools."""

import pytest

from rmcompanion.config import Settings
from rmcompanion.mcp.server import create_mcp_server
from rmcompanion.render.exporter import Exporter
from rmcompanion.store.blob_store import BlobStore
from rmcompanion.store.db import Database


@pytest.fixture
def populated_env(tmp_path):
    settings = Settings(data_dir=tmp_path)
    db = Database(settings=settings)
    blob_store = BlobStore(settings=settings)

    # Insert test documents
    db.upsert_document({
        "id": "doc-alpha",
        "visible_name": "System Architecture Notes",
        "type": "DocumentType",
        "parent_id": "",
        "file_type": "notebook",
        "page_count": 2,
        "doc_hash": "alpha_hash",
    })
    db.set_document_pages("alpha_hash", [
        {"page_idx": 0, "page_id": "page-1", "deleted": False, "redir": -1},
        {"page_idx": 1, "page_id": "page-2", "deleted": False, "redir": -1},
    ])
    db.index_content("doc-alpha", 0, "typed_text", "Technical architecture discussion notes")

    db.upsert_document({
        "id": "folder-work",
        "visible_name": "Work Projects",
        "type": "CollectionType",
        "parent_id": "",
        "file_type": "",
        "page_count": 0,
        "doc_hash": "work_hash",
    })

    exporter = Exporter(db=db, blob_store=blob_store, settings=settings)
    server = create_mcp_server(db=db, blob_store=blob_store, exporter=exporter, settings=settings)
    return server, db


def test_mcp_list_documents(populated_env):
    server, _ = populated_env
    tool_func = server._tool_manager._tools["list_documents"].fn

    docs = tool_func(parent_id="", include_deleted=False)
    assert len(docs) == 2
    names = [d["visible_name"] for d in docs]
    assert "System Architecture Notes" in names
    assert "Work Projects" in names


def test_mcp_search(populated_env):
    server, _ = populated_env
    tool_func = server._tool_manager._tools["search"].fn

    results = tool_func(query="architecture")
    assert len(results) >= 1
    assert results[0]["doc_id"] == "doc-alpha"


def test_mcp_get_document(populated_env):
    server, _ = populated_env
    tool_func = server._tool_manager._tools["get_document"].fn

    doc = tool_func(doc_id="doc-alpha")
    assert doc["visible_name"] == "System Architecture Notes"
    assert len(doc["pages"]) == 2


def test_mcp_sync_status(populated_env):
    server, _ = populated_env
    tool_func = server._tool_manager._tools["sync_status"].fn

    status = tool_func()
    assert "status" in status
    assert "total_blobs" in status


def test_mcp_respects_exclusions(populated_env):
    server, db = populated_env

    # Exclude doc-alpha
    db.set_exclude_from_search("doc-alpha", True)

    list_docs_fn = server._tool_manager._tools["list_documents"].fn
    search_fn = server._tool_manager._tools["search"].fn
    get_doc_fn = server._tool_manager._tools["get_document"].fn
    get_text_fn = server._tool_manager._tools["get_page_text"].fn
    recent_fn = server._tool_manager._tools["recent_changes"].fn

    # list_documents should not return doc-alpha by default
    docs = list_docs_fn(parent_id="", include_deleted=False)
    assert not any(d["id"] == "doc-alpha" for d in docs)

    # list_documents with include_excluded=True should return it
    docs_all = list_docs_fn(parent_id="", include_deleted=False, include_excluded=True)
    assert any(d["id"] == "doc-alpha" for d in docs_all)

    # search should omit doc-alpha
    results = search_fn(query="architecture")
    assert not any(r["doc_id"] == "doc-alpha" for r in results)

    # get_document should raise ValueError
    with pytest.raises(ValueError, match="excluded from AI access"):
        get_doc_fn(doc_id="doc-alpha")

    # get_page_text should raise ValueError
    with pytest.raises(ValueError, match="excluded from AI access"):
        get_text_fn(doc_id="doc-alpha", page_idx=0)

    # recent_changes should omit doc-alpha
    recent = recent_fn(limit=10)
    assert not any(r["id"] == "doc-alpha" for r in recent)


async def test_mcp_writes_are_pushed_to_cloud(tmp_path):
    """MCP edits must reach the tablet the same way web UI edits do."""

    class FakeSync:
        def __init__(self):
            self.calls = []

        def spawn(self, coro):
            self.calls.append(coro.cr_code.co_name)
            coro.close()

        async def push_local_notebook(self, *a): ...
        async def create_remote_folder(self, *a): ...
        async def move_remote_document(self, *a): ...
        async def delete_remote_document(self, *a): ...

    settings = Settings(data_dir=tmp_path)
    fake = FakeSync()
    server = create_mcp_server(settings=settings, sync_engine=fake)
    tools = server._tool_manager._tools

    folder = await tools["create_folder"].fn(name="Inbox")
    await tools["quick_capture"].fn(text="Buy tips", is_task=True)
    await tools["quick_capture"].fn(text="Idea", is_task=False)
    await tools["create_notebook"].fn(title="Fresh")
    await tools["move_document"].fn(doc_id=folder["id"], parent_id="")
    await tools["delete_document"].fn(doc_id=folder["id"])

    assert fake.calls == [
        "create_remote_folder",
        "push_local_notebook",
        "push_local_notebook",
        "push_local_notebook",
        "move_remote_document",
        "delete_remote_document",
    ]
