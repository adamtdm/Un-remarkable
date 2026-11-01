"""Tests for FastAPI REST endpoints and web UI serving."""

import pytest
from fastapi.testclient import TestClient

from rmcompanion.config import Settings
from rmcompanion.web.app import create_app


@pytest.fixture
def test_client(tmp_path):
    settings = Settings(data_dir=tmp_path)
    app = create_app(settings=settings)
    with TestClient(app) as client:
        yield client


def test_api_status(test_client):
    res = test_client.get("/api/status")
    assert res.status_code == 200
    data = res.json()
    assert "sync" in data
    assert "blobs_count" in data


def test_api_documents_and_search(test_client):
    # Empty documents initially
    res = test_client.get("/api/documents")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    # Search endpoint
    search_res = test_client.get("/api/search?q=test")
    assert search_res.status_code == 200
    assert isinstance(search_res.json(), list)


def test_static_index_html(test_client):
    res = test_client.get("/")
    assert res.status_code == 200
    assert "reMarkable Companion" in res.text
    assert "<html" in res.text
    assert 'data-type="folder">Folders<' in res.text
    assert "no-cache" in res.headers.get("cache-control", "")

    # PWA files and cache control
    manifest_res = test_client.get("/manifest.json")
    assert manifest_res.status_code == 200
    assert "reMarkable Companion" in manifest_res.json()["name"]
    assert "no-cache" in manifest_res.headers.get("cache-control", "")

    sw_res = test_client.get("/sw.js")
    assert sw_res.status_code == 200
    assert "rmc-shell" in sw_res.text
    assert "no-store" in sw_res.headers.get("cache-control", "")

    icon_res = test_client.get("/icon.svg")
    assert icon_res.status_code == 200
    assert "<svg" in icon_res.text


def test_api_documents_folder_filter(tmp_path):
    from rmcompanion.store.db import Database
    settings = Settings(data_dir=tmp_path)
    db = Database(settings.db_path)
    db.upsert_document({
        "id": "folder-1",
        "visible_name": "Projects Folder",
        "type": "CollectionType",
        "parent_id": "",
        "file_type": "",
    })
    db.upsert_document({
        "id": "notebook-1",
        "visible_name": "Meeting Notes",
        "type": "DocumentType",
        "parent_id": "",
        "file_type": "notebook",
    })

    app = create_app(settings=settings)
    with TestClient(app) as client:
        # All items
        res_all = client.get("/api/documents")
        assert res_all.status_code == 200
        ids_all = [d["id"] for d in res_all.json()]
        assert "folder-1" in ids_all
        assert "notebook-1" in ids_all

        # Filter by folder
        res_folders = client.get("/api/documents?file_type=folder")
        assert res_folders.status_code == 200
        ids_folders = [d["id"] for d in res_folders.json()]
        assert "folder-1" in ids_folders
        assert "notebook-1" not in ids_folders

        # Filter by notebook
        res_notes = client.get("/api/documents?file_type=notebook")
        assert res_notes.status_code == 200
        ids_notes = [d["id"] for d in res_notes.json()]
        assert "notebook-1" in ids_notes
        assert "folder-1" not in ids_notes
