import pytest
from unittest.mock import AsyncMock, MagicMock

from rmcompanion.cloud.client import RMCloudClient, crc32c
from rmcompanion.config import Settings
from rmcompanion.editor.notebook_editor import NotebookEditor
from rmcompanion.intelligence.task_extractor import TaskExtractor
from rmcompanion.render.exporter import Exporter
from rmcompanion.store.blob_store import BlobStore
from rmcompanion.store.db import Database
from rmcompanion.sync.engine import SyncEngine


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


def test_crc32c_checksum():
    # Standard test vector: ASCII '123456789' has CRC32C 0xE3069283 -> '4waSgw==' in base64
    assert crc32c(b"123456789") == "4waSgw=="


def test_tasks_notebook_always_on_main_page(test_env):
    editor = test_env["editor"]
    db = test_env["db"]

    # 1. Test syncing tasks creates notebook at root (parent_id == "")
    res = editor.sync_tasks_to_notebook(notebook_title="Tasks")
    doc_id = res["id"]
    doc = db.get_document(doc_id)
    assert doc["parent_id"] == ""

    # 2. Test append task keeps parent_id == ""
    res2 = editor.append_task_to_tasks_notebook("Follow up with design team", notebook_title="Tasks")
    doc2 = db.get_document(res2["id"])
    assert doc2["parent_id"] == ""

    # 3. Test creating a folder
    folder = editor.create_folder("Project Archive")
    assert folder["parent_id"] == ""

    # 4. Moving regular document into folder succeeds
    regular_note = editor.create_notebook("Meeting Notes", parent_id="")
    res_move = editor.move_document(regular_note["id"], folder["id"])
    assert res_move["parent_id"] == folder["id"]

    # 5. Moving Tasks notebook into folder is blocked
    with pytest.raises(ValueError, match="The Tasks notebook must remain on the main page"):
        editor.move_document(doc_id, folder["id"])


@pytest.mark.asyncio
async def test_sync_engine_push_document():
    mock_client = MagicMock(spec=RMCloudClient)
    mock_client.upload_document = AsyncMock(return_value={"docID": "test-doc-id", "rootGeneration": 12345})
    mock_auth = MagicMock()
    mock_auth.tokens.is_authenticated = True

    engine = SyncEngine(client=mock_client, auth=mock_auth)
    engine.sync_once = AsyncMock(return_value={"status": "idle"})

    res = await engine.push_document(b"fake-pdf-content", "Test Document", parent_id="")
    assert res["status"] == "ok"
    mock_client.upload_document.assert_awaited_once_with(
        file_bytes=b"fake-pdf-content",
        filename="Test Document",
        parent_id="",
        file_type="pdf",
    )
