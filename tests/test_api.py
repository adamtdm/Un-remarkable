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


def test_cross_site_writes_blocked_without_cors(test_client):
    """Another website must not be able to change the library, and must not be able to read it."""
    blocked = test_client.post("/api/folders", json={"name": "x"}, headers={"Sec-Fetch-Site": "cross-site"})
    assert blocked.status_code == 403

    same_origin = test_client.post("/api/folders", json={"name": "x"}, headers={"Sec-Fetch-Site": "same-origin"})
    assert same_origin.status_code != 403

    no_header = test_client.post("/api/folders", json={"name": "y"})  # curl, scripts, MCP clients
    assert no_header.status_code != 403

    read = test_client.get("/api/documents", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in read.headers


def test_folder_zip_export_streams_from_temp_file(test_client):
    import io
    import zipfile

    import pymupdf

    app = test_client.app
    editor = app.state.notebook_editor
    folder = editor.create_folder("Comics", "")
    pdf = pymupdf.open()
    pdf.new_page()
    editor.import_pdf_file(title="Issue 1", pdf_bytes=pdf.tobytes(), parent_id=folder["id"])

    res = test_client.get(f"/api/documents/{folder['id']}/export/zip")
    assert res.status_code == 200
    assert 'filename="Comics.zip"' in res.headers["content-disposition"]
    assert zipfile.ZipFile(io.BytesIO(res.content)).namelist() == ["Issue 1.pdf"]
    cache_dir = app.state.blob_store.settings.cache_dir
    assert not list(cache_dir.glob("*.zip")), "temp ZIP must be deleted after sending"


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
    assert 'id="reader-page-indicator"' in res.text
    assert 'id="reader-page-input"' in res.text
    assert 'id="reader-page-jump-form"' in res.text
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


def test_api_update_document_position(tmp_path):
    settings = Settings(data_dir=tmp_path)
    app = create_app(settings=settings)
    with TestClient(app) as client:
        # Create a notebook
        nb_res = client.post("/api/documents/new", json={"title": "Position Doc", "initial_text": "Hello"})
        assert nb_res.status_code == 200
        doc_id = nb_res.json()["id"]

        # Update position
        pos_res = client.post(f"/api/documents/{doc_id}/position", json={"page_idx": 0})
        assert pos_res.status_code == 200
        assert pos_res.json()["status"] == "ok"
        assert pos_res.json()["result"]["last_opened_page"] == 0

        # Verify through get_document
        doc_res = client.get(f"/api/documents/{doc_id}")
        assert doc_res.status_code == 200
        assert doc_res.json()["last_opened_page"] == 0



def test_two_page_view_is_remembered_per_document(test_client):
    app = test_client.app
    pdf = __import__("pymupdf").open()
    pdf.new_page()
    pdf.new_page()
    doc_id = app.state.notebook_editor.import_pdf_file(title="Comic", pdf_bytes=pdf.tobytes(), parent_id="")["id"]

    assert test_client.get(f"/api/documents/{doc_id}").json()["two_page"] is False

    res = test_client.post(f"/api/documents/{doc_id}/view", json={"two_page": True})
    assert res.status_code == 200
    assert test_client.get(f"/api/documents/{doc_id}").json()["two_page"] is True

    # A cloud sync rewrites the document row; the reader setting must survive it.
    db = app.state.db
    db.upsert_document({**db.get_document(doc_id), "visible_name": "Comic (synced)"})
    assert test_client.get(f"/api/documents/{doc_id}").json()["two_page"] is True

    assert test_client.post("/api/documents/missing/view", json={"two_page": True}).status_code == 404
