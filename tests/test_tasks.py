"""Tests for Phase 3 task extraction, consolidation, and vision settings."""

from fastapi.testclient import TestClient

from rmcompanion.config import Settings
from rmcompanion.intelligence.task_extractor import (
    TaskExtractor,
    extract_tasks_from_text,
)
from rmcompanion.mcp.server import create_mcp_server
from rmcompanion.render.exporter import Exporter
from rmcompanion.store.blob_store import BlobStore
from rmcompanion.store.db import Database
from rmcompanion.web.app import create_app


def test_rule_based_task_parsing():
    sample = """
    Project kickoff meeting.
    * Review system architecture diagram with lead engineer. Next sentence.
    * Buy new stylus tips for Paper Pro.
    - [ ] Set up Docker volumes and cron jobs
    - [x] Pair reMarkable account via one-time code
    TODO: finalize contract review by Friday
    Regular body text explaining project milestones.
    """

    tasks = extract_tasks_from_text(sample)
    assert len(tasks) == 5

    # 1. Asterisk with sentence stop
    assert tasks[0]["text"] == "Review system architecture diagram with lead engineer."
    assert tasks[0]["marker"] == "star"
    assert tasks[0]["status"] == "open"

    # 2. Asterisk 2
    assert tasks[1]["text"] == "Buy new stylus tips for Paper Pro."
    assert tasks[1]["marker"] == "star"

    # 3. Open Checkbox
    assert tasks[2]["text"] == "Set up Docker volumes and cron jobs"
    assert tasks[2]["marker"] == "checkbox"
    assert tasks[2]["status"] == "open"

    # 4. Completed Checkbox
    assert tasks[3]["text"] == "Pair reMarkable account via one-time code"
    assert tasks[3]["marker"] == "checkbox"
    assert tasks[3]["status"] == "completed"

    # 5. TODO marker
    assert tasks[4]["text"] == "finalize contract review by Friday"
    assert tasks[4]["marker"] == "todo"
    assert tasks[4]["status"] == "open"


def test_task_database_and_deduplication(tmp_path):
    settings = Settings(data_dir=tmp_path)
    db = Database(settings=settings)
    blob_store = BlobStore(settings=settings)
    exporter = Exporter(db=db, blob_store=blob_store, settings=settings)

    extractor = TaskExtractor(db=db, blob_store=blob_store, exporter=exporter)

    doc_id = "doc-meeting-123"
    text = "* Call client about deliverables. Some extra text."

    # First extraction
    tasks1 = extractor.extract_from_typed_page(doc_id, page_idx=0, typed_text=text)
    assert len(tasks1) == 1
    task_id = tasks1[0]["id"]

    assert db.count_open_tasks() == 1
    all_open = db.list_tasks(status="open")
    assert len(all_open) == 1
    assert all_open[0]["clean_text"] == "Call client about deliverables"

    # Second extraction on the same content should NOT duplicate task
    tasks2 = extractor.extract_from_typed_page(doc_id, page_idx=0, typed_text=text)
    assert len(tasks2) == 1
    assert db.count_open_tasks() == 1

    # Mark completed
    ok = db.set_task_status(task_id, "completed")
    assert ok is True
    assert db.count_open_tasks() == 0

    all_completed = db.list_tasks(status="completed")
    assert len(all_completed) == 1
    assert all_completed[0]["id"] == task_id


def test_tasks_api_endpoints(tmp_path):
    settings = Settings(data_dir=tmp_path)
    app = create_app(settings=settings)
    client = TestClient(app)

    db = app.state.db
    # Create task directly
    db.upsert_task({
        "id": "t-1",
        "doc_id": "d-1",
        "page_idx": 0,
        "raw_text": "* Finish Phase 3 plan.",
        "clean_text": "Finish Phase 3 plan",
        "status": "open",
        "marker_type": "star",
        "fingerprint": "fp1",
    })

    # List tasks
    res = client.get("/api/tasks")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["clean_text"] == "Finish Phase 3 plan"

    # Update status
    up_res = client.post("/api/tasks/t-1/status", json={"status": "completed"})
    assert up_res.status_code == 200
    assert up_res.json()["status"] == "completed"

    # Check status=open is now 0
    res_open = client.get("/api/tasks?status=open")
    assert len(res_open.json()) == 0

    # Vision settings
    settings_res = client.get("/api/settings/vision")
    assert settings_res.status_code == 200
    assert settings_res.json()["api_key_set"] is False

    save_res = client.post("/api/settings/vision", json={
        "provider": "gemini",
        "model": "gemini-flash-lite-latest",
        "api_key": "AIzaSyTest1234567890",
    })
    assert save_res.status_code == 200

    settings_after = client.get("/api/settings/vision").json()
    assert settings_after["api_key_set"] is True
    assert "AIza" in settings_after["api_key_masked"]


def test_mcp_task_tools(tmp_path):
    settings = Settings(data_dir=tmp_path)
    db = Database(settings=settings)
    blob_store = BlobStore(settings=settings)
    exporter = Exporter(db=db, blob_store=blob_store, settings=settings)

    db.upsert_task({
        "id": "mcp-t1",
        "doc_id": "d-mcp",
        "page_idx": 1,
        "raw_text": "- [ ] Review MCP task tool implementation",
        "clean_text": "Review MCP task tool implementation",
        "status": "open",
        "marker_type": "checkbox",
        "fingerprint": "fpmcp1",
    })

    server = create_mcp_server(db=db, blob_store=blob_store, exporter=exporter, settings=settings)
    tools = {t.name: t for t in server._tool_manager.list_tools()}
    assert "list_tasks" in tools
    assert "complete_task" in tools


def test_layout_task_pages_groups_by_source_and_paginates():
    from rmcompanion.editor.notebook_editor import layout_task_pages

    tasks = [{"clean_text": f"Meeting task {i}", "doc_name": "Weekly sync", "created_at": i} for i in range(20)]
    tasks.append({"clean_text": "Call the bank", "doc_name": None, "created_at": 0})

    pages = layout_task_pages("Tasks", tasks, max_lines=10)

    assert len(pages) == 3
    assert pages[0].startswith("Tasks - 21 open - page 1/3")
    body = [p.split("\n\n", 1)[1].split("\n") for p in pages]
    assert all(len(lines) <= 10 for lines in body)
    assert body[0][:2] == ["Captured", "[ ] Call the bank"]  # captured tasks come first
    assert body[1][0] == "Weekly sync"  # a group continued on a new page gets its heading again
    assert sum(line.startswith("[ ] ") for lines in body for line in lines) == 21


def test_layout_task_pages_empty():
    from rmcompanion.editor.notebook_editor import layout_task_pages

    assert layout_task_pages("Tasks", []) == ["Tasks - 0 open - page 1/1\n\nNo open tasks."]


def test_tasks_notebook_is_one_document_and_never_mines_itself(tmp_path):
    from rmcompanion.config import Settings
    from rmcompanion.editor.notebook_editor import NotebookEditor
    from rmcompanion.intelligence.task_extractor import TaskExtractor
    from rmcompanion.render.exporter import Exporter
    from rmcompanion.store.blob_store import BlobStore
    from rmcompanion.store.db import Database

    settings = Settings(data_dir=tmp_path)
    db = Database(settings=settings)
    blob_store = BlobStore(settings=settings)
    extractor = TaskExtractor(db=db, blob_store=blob_store, exporter=Exporter(db=db, blob_store=blob_store, settings=settings))
    editor = NotebookEditor(db=db, blob_store=blob_store, task_extractor=extractor)

    ids = {editor.append_task_to_tasks_notebook(f"Task number {i}")["id"] for i in range(40)}
    res = editor.sync_tasks_to_notebook()

    assert ids == {res["id"]}, "every rebuild must reuse the same notebook"
    assert res["task_count"] == 40, "the notebook's own lines must not be re-extracted as new tasks"
    assert res["page_count"] > 1
    assert len([d for d in db.list_documents() if d["visible_name"] == "Tasks"]) == 1


def test_crossed_out_task_is_completed_on_rescan(tmp_path):
    from rmcompanion.config import Settings
    from rmcompanion.store.db import Database

    db = Database(settings=Settings(data_dir=tmp_path))
    base = {"doc_id": "d1", "page_idx": 0, "raw_text": "x", "clean_text": "x", "fingerprint": "fp", "created_at": 1.0}
    db.upsert_task({**base, "id": "t1", "status": "open"})
    db.upsert_task({**base, "id": "t2", "status": "completed"})
    db.upsert_task({**base, "id": "t3", "status": "open"})

    tasks = db.list_tasks()
    assert [(t["id"], t["status"]) for t in tasks] == [("t1", "completed")]


def test_page_order_keys_sort_in_page_order():
    from rmcompanion.editor.notebook_editor import page_order_key

    keys = [page_order_key(i) for i in range(1000)]
    assert keys == sorted(keys)
    assert len(set(keys)) == 1000
