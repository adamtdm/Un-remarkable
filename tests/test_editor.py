"""Tests for Phase 4 typed notebook editor and markdown import."""

import pytest

from rmcompanion.config import Settings
from rmcompanion.editor.notebook_editor import NotebookEditor, extract_page_typed_text
from rmcompanion.intelligence.task_extractor import TaskExtractor
from rmcompanion.render.exporter import Exporter
from rmcompanion.store.blob_store import BlobStore
from rmcompanion.store.db import Database


@pytest.fixture
def test_env(tmp_path):
    settings = Settings(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache")
    db = Database(db_path=tmp_path / "test.db", settings=settings)
    blob_store = BlobStore(settings=settings)
    exporter = Exporter(db=db, blob_store=blob_store, settings=settings)
    task_extractor = TaskExtractor(db=db, blob_store=blob_store, exporter=exporter)
    editor = NotebookEditor(db=db, blob_store=blob_store, task_extractor=task_extractor)
    return {
        "db": db,
        "blob_store": blob_store,
        "exporter": exporter,
        "task_extractor": task_extractor,
        "editor": editor,
    }


def test_create_notebook(test_env):
    editor = test_env["editor"]
    db = test_env["db"]

    res = editor.create_notebook(
        title="Weekly Sprint",
        initial_text="Sprint goals:\n- [ ] Deliver Phase 4\n* Complete testing.",
    )

    doc_id = res["id"]
    assert res["visible_name"] == "Weekly Sprint"
    assert res["page_count"] == 1

    doc = db.get_document(doc_id)
    assert doc is not None
    assert doc["visible_name"] == "Weekly Sprint"
    assert len(doc["pages"]) == 1
    assert len(doc["files"]) == 4  # .rm, .content, .metadata, .pagedata

    # Test extracting typed text
    extracted = editor.get_page_typed_text(doc_id, 0)
    assert "Deliver Phase 4" in extracted
    assert "Complete testing." in extracted

    # Test task auto-extraction from typed text
    tasks = db.list_tasks(doc_id=doc_id)
    assert len(tasks) == 2


def test_update_page_typed_text(test_env):
    editor = test_env["editor"]
    db = test_env["db"]

    res = editor.create_notebook(title="Meeting Notes", initial_text="Initial line.")
    doc_id = res["id"]

    # Update text
    updated = editor.update_page_typed_text(
        doc_id=doc_id,
        page_idx=0,
        text="Updated line 1.\n- [ ] Follow up with client\n- [x] Send invoices",
    )
    assert updated["id"] == doc_id
    assert updated["page_idx"] == 0

    # Verify extracted text
    text = editor.get_page_typed_text(doc_id, 0)
    assert "Follow up with client" in text

    # Verify tasks updated
    tasks = db.list_tasks(doc_id=doc_id)
    assert len(tasks) == 2
    statuses = {t["clean_text"]: t["status"] for t in tasks}
    assert statuses["Follow up with client"] == "open"
    assert statuses["Send invoices"] == "completed"


def test_tasks_notebook_sync(test_env):
    editor = test_env["editor"]
    db = test_env["db"]

    # Append tasks to dedicated "Tasks" notebook
    res1 = editor.append_task_to_tasks_notebook("Order replacement pen tips")
    assert res1["visible_name"] == "Tasks"

    res2 = editor.append_task_to_tasks_notebook("Configure Tailscale on server")
    assert res2["visible_name"] == "Tasks"

    text = editor.get_page_typed_text(res1["id"], 0)
    assert "Order replacement pen tips" in text
    assert "Configure Tailscale on server" in text


def test_import_markdown(test_env):
    editor = test_env["editor"]
    db = test_env["db"]

    md_content = """# Section 1
Welcome to page 1.
- [ ] Task on page 1

---

# Section 2
Welcome to page 2.
- [ ] Task on page 2
"""
    res = editor.import_markdown(title="Multi-page Spec", markdown_content=md_content)
    doc_id = res["id"]
    assert res["page_count"] == 2

    # Verify page 0 and page 1
    p0_text = editor.get_page_typed_text(doc_id, 0)
    assert "Welcome to page 1" in p0_text

    p1_text = editor.get_page_typed_text(doc_id, 1)
    assert "Welcome to page 2" in p1_text

    # Tasks across pages
    tasks = db.list_tasks(doc_id=doc_id)
    assert len(tasks) == 2


def test_api_editor_endpoints(test_env):
    from fastapi.testclient import TestClient
    from rmcompanion.web.app import create_app

    settings = Settings(data_dir=test_env["db"].settings.data_dir, cache_dir=test_env["db"].settings.cache_dir)
    app = create_app(settings)
    app.state.db = test_env["db"]
    app.state.blob_store = test_env["blob_store"]
    app.state.notebook_editor = test_env["editor"]

    client = TestClient(app)

    # 1. Create notebook
    resp = client.post("/api/documents/new", json={"title": "Test Web Doc", "initial_text": "Hello world\n- [ ] Web task"})
    assert resp.status_code == 200
    data = resp.json()
    doc_id = data["id"]
    assert data["visible_name"] == "Test Web Doc"

    # 2. Get text
    resp_get = client.get(f"/api/documents/{doc_id}/pages/0/text")
    assert resp_get.status_code == 200
    assert "Web task" in resp_get.json()["text"]

    # 3. Update text
    resp_put = client.put(f"/api/documents/{doc_id}/pages/0/text", json={"text": "Updated content\n- [x] Web task"})
    assert resp_put.status_code == 200
    assert resp_put.json()["ok"] is True

    # 4. Import markdown
    resp_md = client.post("/api/documents/import-markdown", json={"title": "Imported MD", "markdown": "# Title\nContent"})
    assert resp_md.status_code == 200
    assert resp_md.json()["visible_name"] == "Imported MD"

    # 5. Append task item
    resp_task = client.post("/api/tasks/create-item", json={"text": "Buy reMarkable Marker Plus", "notebook_title": "Tasks"})
    assert resp_task.status_code == 200
    assert resp_task.json()["ok"] is True


async def test_mcp_editor_tools(test_env):
    from rmcompanion.mcp.server import create_mcp_server

    server = create_mcp_server(
        db=test_env["db"],
        blob_store=test_env["blob_store"],
        task_extractor=test_env["task_extractor"],
        notebook_editor=test_env["editor"],
    )

    tool_list = await server.list_tools()
    tools = {t.name: t for t in tool_list}
    assert "create_notebook" in tools
    assert "append_task" in tools
    assert "update_page_text" in tools
    assert "list_folders" in tools
    assert "create_folder" in tools
    assert "move_document" in tools
    assert "delete_document" in tools


def test_create_and_nest_folders(test_env):
    editor = test_env["editor"]
    db = test_env["db"]

    # Create root folder
    f1 = editor.create_folder(name="Projects")
    assert f1["visible_name"] == "Projects"
    assert f1["type"] == "CollectionType"
    assert f1["parent_id"] == ""

    # Create nested folder
    f2 = editor.create_folder(name="Subproject Alpha", parent_id=f1["id"])
    assert f2["visible_name"] == "Subproject Alpha"
    assert f2["parent_id"] == f1["id"]

    # Verify folder tree
    tree = db.get_folder_tree()
    assert len(tree) == 2
    paths = {item["visible_name"]: item["path"] for item in tree}
    assert paths["Projects"] == "Projects"
    assert paths["Subproject Alpha"] == "Projects / Subproject Alpha"


def test_move_document_and_folder(test_env):
    editor = test_env["editor"]
    db = test_env["db"]

    f_parent = editor.create_folder(name="Work")
    f_child = editor.create_folder(name="Tasks", parent_id=f_parent["id"])
    note = editor.create_notebook(title="Daily Standup", initial_text="Notes here")

    # Move note into nested child folder
    res = editor.move_document(note["id"], f_child["id"])
    assert res["parent_id"] == f_child["id"]
    updated_note = db.get_document(note["id"])
    assert updated_note["parent_id"] == f_child["id"]

    # Move child folder to root
    editor.move_document(f_child["id"], "")
    updated_child = db.get_document(f_child["id"])
    assert updated_child["parent_id"] == ""

    # Prevent moving folder into itself
    with pytest.raises(ValueError, match="Cannot move a folder into itself"):
        editor.move_document(f_parent["id"], f_parent["id"])

    # Prevent moving folder into its own subfolder
    editor.move_document(f_child["id"], f_parent["id"])
    with pytest.raises(ValueError, match="Cannot move a folder into its own subfolder"):
        editor.move_document(f_parent["id"], f_child["id"])


def test_delete_document_and_recursive_folder(test_env):
    editor = test_env["editor"]
    db = test_env["db"]

    folder = editor.create_folder(name="Archive")
    subfolder = editor.create_folder(name="2025", parent_id=folder["id"])
    doc = editor.create_notebook(title="Annual Review", parent_id=subfolder["id"])

    # Deleting the parent folder should soft-delete all descendants
    res = editor.delete_document(folder["id"])
    assert folder["id"] in res["deleted_ids"]
    assert subfolder["id"] in res["deleted_ids"]
    assert doc["id"] in res["deleted_ids"]

    # They should no longer appear in non-deleted listings
    active_docs = db.list_documents()
    active_ids = {d["id"] for d in active_docs}
    assert folder["id"] not in active_ids
    assert subfolder["id"] not in active_ids
    assert doc["id"] not in active_ids


def test_api_folder_and_move_delete_endpoints(test_env):
    from fastapi.testclient import TestClient
    from rmcompanion.web.app import create_app

    settings = Settings(data_dir=test_env["db"].settings.data_dir)
    app = create_app(settings=settings)
    app.state.db = test_env["db"]
    app.state.blob_store = test_env["blob_store"]
    app.state.notebook_editor = test_env["editor"]

    client = TestClient(app)

    # 1. Create folder via API
    resp_f = client.post("/api/folders", json={"name": "Research", "parent_id": ""})
    assert resp_f.status_code == 200
    folder_id = resp_f.json()["folder"]["id"]

    # 2. List folders
    resp_list = client.get("/api/folders")
    assert resp_list.status_code == 200
    assert any(f["id"] == folder_id for f in resp_list.json())

    # 3. Create doc and move via API
    resp_doc = client.post("/api/documents/new", json={"title": "Paper Draft", "initial_text": "Draft"})
    doc_id = resp_doc.json()["id"]

    resp_move = client.post(f"/api/documents/{doc_id}/move", json={"parent_id": folder_id})
    assert resp_move.status_code == 200
    assert resp_move.json()["result"]["parent_id"] == folder_id

    # 4. Delete doc via API
    resp_del = client.delete(f"/api/documents/{doc_id}")
    assert resp_del.status_code == 200
    assert resp_del.json()["status"] == "ok"

    # Confirm doc is gone
    resp_check = client.get(f"/api/documents/{doc_id}")
    assert resp_check.status_code == 200
    assert resp_check.json()["deleted"] is True


def test_quick_capture_notes_and_tasks(test_env):
    editor = test_env["editor"]
    db = test_env["db"]

    # 1. Quick capture task
    res_task = editor.append_task_to_tasks_notebook("Order replacement marker tips")
    assert res_task["visible_name"] == "Tasks"
    tasks = db.list_tasks()
    assert any("Order replacement marker tips" in t["clean_text"] for t in tasks)

    # 2. Quick capture note
    res_note = editor.append_note_to_notebook("Remember to calibrate color display on Paper Pro")
    assert res_note["visible_name"] == "Quick Notes"
    doc_id = res_note["id"]
    text = editor.get_page_typed_text(doc_id, 0)
    assert "calibrate color display" in text


def test_update_document_position(test_env):
    import json
    editor = test_env["editor"]
    db = test_env["db"]
    blob_store = test_env["blob_store"]

    res = editor.create_notebook(title="Position Test", initial_text="P1", pages_content=["Page 1", "Page 2", "Page 3"])
    doc_id = res["id"]

    doc = db.get_document(doc_id)
    assert doc["last_opened_page"] == 0

    pos_res = editor.update_document_position(doc_id, 2)
    assert pos_res["id"] == doc_id
    assert pos_res["last_opened_page"] == 2

    # Verify database was updated
    updated_doc = db.get_document(doc_id)
    assert updated_doc["last_opened_page"] == 2

    # Verify metadata blob was updated
    meta_file = next(f for f in updated_doc["files"] if f["file_id"].endswith(".metadata"))
    meta_dict = json.loads(blob_store.get(meta_file["blob_hash"]).decode("utf-8"))
    assert meta_dict["lastOpenedPage"] == 2

    # Verify content blob was updated
    content_file = next((f for f in updated_doc["files"] if f["file_id"].endswith(".content")), None)
    if content_file:
        content_dict = json.loads(blob_store.get(content_file["blob_hash"]).decode("utf-8"))
        if "cPages" in content_dict and "lastOpened" in content_dict["cPages"]:
            assert content_dict["cPages"]["lastOpened"]["value"] == updated_doc["pages"][2]["page_id"]


