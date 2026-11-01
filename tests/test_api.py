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
    assert "Un-remarkable" in res.text
    assert "<html" in res.text
    assert 'data-type="folder">Folders<' in res.text
    assert "no-cache" in res.headers.get("cache-control", "")

    # PWA files and cache control
    manifest_res = test_client.get("/manifest.json")
    assert manifest_res.status_code == 200
    assert "Un-remarkable" in manifest_res.json()["name"]
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


def test_api_thumbnail_and_quick_capture(tmp_path):
    settings = Settings(data_dir=tmp_path)
    app = create_app(settings=settings)
    with TestClient(app) as client:
        # Create a document
        create_res = client.post("/api/documents/new", json={"title": "Ideas", "initial_text": "First idea."})
        assert create_res.status_code == 200
        doc_id = create_res.json()["id"]

        # 1. Fetch thumbnail
        thumb_res = client.get(f"/api/documents/{doc_id}/thumbnail")
        assert thumb_res.status_code == 200
        assert thumb_res.headers.get("content-type") == "image/png"
        assert "ETag" in thumb_res.headers
        etag = thumb_res.headers["ETag"]

        # ETag 304 response
        cached_res = client.get(f"/api/documents/{doc_id}/thumbnail", headers={"If-None-Match": etag})
        assert cached_res.status_code == 304

        # 2. Quick capture task endpoint
        qc_task_res = client.post("/api/notes/quick-capture", json={"text": "Review budget figures", "is_task": True})
        assert qc_task_res.status_code == 200
        assert qc_task_res.json()["ok"] is True

        # 3. Quick capture note endpoint
        qc_note_res = client.post("/api/notes/quick-capture", json={"text": "Summary of research paper", "is_task": False})
        assert qc_note_res.status_code == 200
        assert qc_note_res.json()["ok"] is True


def test_bulk_import_and_zip_export(tmp_path):
    import io
    import zipfile

    settings = Settings(data_dir=tmp_path)
    app = create_app(settings=settings)
    with TestClient(app) as client:
        md_file = ("notes.md", b"# Bulk Note\nHello bulk world", "text/markdown")
        res = client.post(
            "/api/documents/bulk-import",
            files=[("files", md_file)],
            data={"device": "none", "parent_id": ""},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["ok"] is True
        assert data["imported_count"] == 1
        doc_id = data["imported"][0]["id"]

        zip_res = client.get(f"/api/documents/{doc_id}/export/zip")
        assert zip_res.status_code == 200
        assert zip_res.headers["content-type"] == "application/zip"

        zf = zipfile.ZipFile(io.BytesIO(zip_res.content))
        names = zf.namelist()
        assert len(names) >= 1


def test_rescan_endpoint(test_client):
    res = test_client.post("/api/settings/rescan")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "rescanned_count" in data
    assert "excluded_count" in data

