"""Tests for BlobStore and Database."""

import hashlib

import pytest

from rmcompanion.config import Settings
from rmcompanion.store.blob_store import BlobStore
from rmcompanion.store.db import Database


@pytest.fixture
def temp_settings(tmp_path):
    return Settings(data_dir=tmp_path)


def test_blob_store(temp_settings):
    store = BlobStore(settings=temp_settings)
    data = b"Hello reMarkable Companion"
    h = hashlib.sha256(data).hexdigest()

    assert not store.has(h)
    p = store.put(h, data, verify=True)
    assert p.is_file()
    assert store.has(h)
    assert store.get(h) == data

    # Verify fails on corrupt data
    with pytest.raises(ValueError):
        store.put(h, b"different data", verify=True)

    count, total_size = store.stats()
    assert count == 1
    assert total_size == len(data)


def test_database_crud_and_search(temp_settings):
    db = Database(settings=temp_settings)

    # State
    db.set_state("test_key", "test_val")
    assert db.get_state("test_key") == "test_val"

    # Upsert document
    doc_data = {
        "id": "doc-uuid-1",
        "visible_name": "Project Roadmap 2026",
        "type": "DocumentType",
        "parent_id": "",
        "file_type": "notebook",
        "page_count": 3,
        "doc_hash": "hash1234",
    }
    db.upsert_document(doc_data)

    retrieved = db.get_document("doc-uuid-1")
    assert retrieved is not None
    assert retrieved["visible_name"] == "Project Roadmap 2026"
    assert retrieved["page_count"] == 3

    # Add pages and files
    db.set_document_pages("hash1234", [
        {"page_idx": 0, "page_id": "page-1", "deleted": False, "redir": -1},
        {"page_idx": 1, "page_id": "page-2", "deleted": False, "redir": -1},
    ])
    doc_with_pages = db.get_document("doc-uuid-1")
    assert len(doc_with_pages["pages"]) == 2

    # Full text search test
    db.index_content("doc-uuid-1", 0, "typed_text", "We need to finalize the quarterly release goals.")
    results = db.search("quarterly")
    assert len(results) >= 1
    assert results[0]["doc_id"] == "doc-uuid-1"
    assert "quarterly" in results[0]["snippet"].lower()

    # Search by title
    title_results = db.search("Roadmap")
    assert len(title_results) >= 1
    assert title_results[0]["doc_id"] == "doc-uuid-1"
