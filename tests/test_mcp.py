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
        "visible_name": "Antigravity Research Notes",
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
    db.index_content("doc-alpha", 0, "typed_text", "Agent architecture discussion with Claude")

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
    assert "Antigravity Research Notes" in names
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
    assert doc["visible_name"] == "Antigravity Research Notes"
    assert len(doc["pages"]) == 2


def test_mcp_sync_status(populated_env):
    server, _ = populated_env
    tool_func = server._tool_manager._tools["sync_status"].fn

    status = tool_func()
    assert "status" in status
    assert "total_blobs" in status
