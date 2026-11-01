"""Model Context Protocol (MCP) server exposing reMarkable library tools to AI clients."""

from __future__ import annotations

import logging
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.utilities.types import Image

from rmcompanion.config import Settings, get_settings
from rmcompanion.editor.notebook_editor import NotebookEditor
from rmcompanion.intelligence.task_extractor import TaskExtractor
from rmcompanion.render.exporter import Exporter
from rmcompanion.store.blob_store import BlobStore
from rmcompanion.store.db import Database
from rmcompanion.sync.engine import SyncEngine

logger = logging.getLogger(__name__)


def create_mcp_server(
    db: Database | None = None,
    blob_store: BlobStore | None = None,
    exporter: Exporter | None = None,
    sync_engine: SyncEngine | None = None,
    task_extractor: TaskExtractor | None = None,
    notebook_editor: NotebookEditor | None = None,
    settings: Settings | None = None,
) -> MCPServer:
    """Create and configure MCPServer instance with all reMarkable tools."""
    app_settings = settings or get_settings()
    app_db = db or Database(settings=app_settings)
    app_blobs = blob_store or BlobStore(settings=app_settings)
    app_exporter = exporter or Exporter(db=app_db, blob_store=app_blobs, settings=app_settings)
    app_editor = notebook_editor or NotebookEditor(
        db=app_db,
        blob_store=app_blobs,
        task_extractor=task_extractor,
    )

    server = MCPServer(
        name="remarkable-companion",
        title="reMarkable Paper Pro Companion",
        description="Search, read, and inspect handwritten notebooks, PDFs, and notes mirrored from your reMarkable tablet.",
        version="0.1.0",
    )

    @server.tool(
        name="list_documents",
        description="List documents and folders in your reMarkable library. Optionally filter by parent folder.",
    )
    def list_documents(
        parent_id: str = "",
        include_deleted: bool = False,
        file_type: str = "",
    ) -> list[dict[str, Any]]:
        """List documents and folders.

        Args:
            parent_id: Folder UUID, or empty string "" for the root library.
            include_deleted: Whether to include documents currently in the trash.
            file_type: Optional filter: 'folder', 'notebook', 'pdf', or 'epub'.
        """
        pid = parent_id if parent_id else ""
        ft = file_type if file_type else None
        docs = app_db.list_documents(parent_id=pid, include_deleted=include_deleted, file_type=ft)
        return [
            {
                "id": d["id"],
                "visible_name": d["visible_name"],
                "type": d["type"],
                "file_type": d["file_type"],
                "page_count": d["page_count"],
                "last_modified": d["last_modified"],
                "pinned": bool(d["pinned"]),
                "parent_id": d["parent_id"],
            }
            for d in docs
        ]

    @server.tool(
        name="search",
        description="Search across all notebooks, typed text, tags, and PDF text in your reMarkable library.",
    )
    def search(query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search your library.

        Args:
            query: Keywords or phrases to search for.
            limit: Maximum number of search results to return (default 20).
        """
        return app_db.search(query=query, limit=limit)

    @server.tool(
        name="get_document",
        description="Get detailed metadata, page index list, and tags for a specific document.",
    )
    def get_document(doc_id: str) -> dict[str, Any]:
        """Get document details.

        Args:
            doc_id: UUID of the document.
        """
        doc = app_db.get_document(doc_id)
        if not doc:
            raise ValueError(f"Document with ID {doc_id} was not found")

        # Exclude large internal file blobs list from general MCP payload
        return {
            "id": doc["id"],
            "visible_name": doc["visible_name"],
            "type": doc["type"],
            "file_type": doc["file_type"],
            "parent_id": doc["parent_id"],
            "last_modified": doc["last_modified"],
            "last_opened_page": doc["last_opened_page"],
            "pinned": bool(doc["pinned"]),
            "page_count": doc["page_count"],
            "tags": doc.get("tags", []),
            "pages": [
                {"page_idx": p["page_idx"], "page_id": p["page_id"], "redir": p.get("redir", -1)}
                for p in doc.get("pages", [])
                if not p.get("deleted")
            ],
        }

    @server.tool(
        name="get_page_text",
        description="Extract typed notes or PDF body text for a specific page of a document.",
    )
    def get_page_text(doc_id: str, page_idx: int = 0) -> dict[str, Any]:
        """Get text extracted from a page.

        Args:
            doc_id: UUID of the document.
            page_idx: 0-based page index.
        """
        with app_db.connect() as conn:
            rows = conn.execute(
                "SELECT source, content FROM search_index WHERE doc_id = ? AND page_idx = ? AND source != 'title'",
                (doc_id, page_idx),
            ).fetchall()

        text_sections = [dict(r) for r in rows]
        combined = "\n\n".join(r["content"] for r in text_sections)
        return {
            "doc_id": doc_id,
            "page_idx": page_idx,
            "has_text": bool(combined),
            "text": combined,
            "sections": text_sections,
        }

    @server.tool(
        name="get_page_image",
        description="Render a page as a high-resolution PNG image for visual inspection and handwriting OCR.",
    )
    def get_page_image(doc_id: str, page_idx: int = 0, dark_mode: bool = False) -> Image:
        """Render a page as a PNG image.

        Args:
            doc_id: UUID of the document.
            page_idx: 0-based page index.
            dark_mode: Whether to render with dark mode colors (default False).
        """
        png_bytes = app_exporter.render_page_png(doc_id, page_idx=page_idx, dark_mode=dark_mode)
        return Image(data=png_bytes, format="png")

    @server.tool(
        name="recent_changes",
        description="Get a list of documents that were modified or synced recently.",
    )
    def recent_changes(limit: int = 15) -> list[dict[str, Any]]:
        """List recently modified documents."""
        with app_db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, visible_name, type, file_type, last_modified, updated_at
                FROM documents
                WHERE deleted = 0
                ORDER BY updated_at DESC, last_modified DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    @server.tool(
        name="sync_status",
        description="Check current cloud sync status, generation number, and last sync timestamp.",
    )
    def sync_status() -> dict[str, Any]:
        """Get current synchronization status."""
        return {
            "status": app_db.get_state("sync_status", "idle"),
            "last_sync_time": float(app_db.get_state("last_sync_time", "0")),
            "last_generation": int(app_db.get_state("last_generation", "0")),
            "last_root_hash": app_db.get_state("last_root_hash", ""),
            "last_error": app_db.get_state("sync_error", ""),
            "total_blobs": app_blobs.stats()[0],
            "total_blob_bytes": app_blobs.stats()[1],
        }

    @server.tool(
        name="list_tasks",
        description="List consolidated tasks extracted from notebooks and notes.",
    )
    def list_tasks(status: str = "open", doc_id: str = "") -> list[dict[str, Any]]:
        """List tasks.

        Args:
            status: Optional filter: 'open' or 'completed' (default 'open').
            doc_id: Optional document ID to filter tasks by source.
        """
        st = status if status in {"open", "completed"} else None
        did = doc_id if doc_id else None
        return app_db.list_tasks(status=st, doc_id=did)

    @server.tool(
        name="complete_task",
        description="Mark an action item or task as completed.",
    )
    def complete_task(task_id: str) -> dict[str, Any]:
        """Mark task completed.

        Args:
            task_id: The ID of the task to complete.
        """
        ok = app_db.set_task_status(task_id, "completed")
        return {"ok": ok, "task_id": task_id, "status": "completed"}

    @server.tool(
        name="create_notebook",
        description="Create a new native reMarkable notebook with initial typed text.",
    )
    def create_notebook(title: str, text: str = "", parent_id: str = "") -> dict[str, Any]:
        """Create a new notebook.

        Args:
            title: The visible title of the notebook.
            text: Initial typed content for the first page.
            parent_id: Optional parent folder UUID.
        """
        return app_editor.create_notebook(title=title, initial_text=text, parent_id=parent_id)

    @server.tool(
        name="append_task",
        description="Append an action item or task checkbox to the synced reMarkable Tasks notebook.",
    )
    def append_task(text: str, notebook_title: str = "Tasks") -> dict[str, Any]:
        """Append a task to the Tasks notebook.

        Args:
            text: The task description to add (e.g. 'Order stylus replacement tips').
            notebook_title: Target notebook title (defaults to 'Tasks').
        """
        return app_editor.append_task_to_tasks_notebook(task_text=text, notebook_title=notebook_title)

    @server.tool(
        name="quick_capture",
        description="Quickly capture a note entry or action item to your reMarkable tablet.",
    )
    def quick_capture(
        text: str,
        is_task: bool = True,
        notebook_title: str = "",
    ) -> dict[str, Any]:
        """Instantly capture a thought or task to the tablet.

        Args:
            text: The content to capture.
            is_task: Whether to format and append as an action item task checkbox (default True).
            notebook_title: Target notebook title (defaults to 'Tasks' for tasks, 'Quick Notes' for notes).
        """
        if is_task:
            return app_editor.append_task_to_tasks_notebook(task_text=text, notebook_title=notebook_title or "Tasks")
        else:
            return app_editor.append_note_to_notebook(text=text, notebook_title=notebook_title or "Quick Notes")

    @server.tool(
        name="update_page_text",
        description="Update or replace typed text on a specific page of a reMarkable notebook.",
    )
    def update_page_text(doc_id: str, page_idx: int, text: str) -> dict[str, Any]:
        """Update typed text of a page.

        Args:
            doc_id: UUID of the notebook document.
            page_idx: Zero-based page index.
            text: The full new typed text for the page.
        """
        return app_editor.update_page_typed_text(doc_id=doc_id, page_idx=page_idx, text=text)

    @server.tool(
        name="list_folders",
        description="List all folders in the reMarkable library including full nesting paths and hierarchy.",
    )
    def list_folders() -> list[dict[str, Any]]:
        """List folders with hierarchical path, depth, and IDs."""
        return app_db.get_folder_tree()

    @server.tool(
        name="create_folder",
        description="Create a new folder or nested subfolder in the reMarkable library.",
    )
    def create_folder(name: str, parent_id: str = "") -> dict[str, Any]:
        """Create a folder.

        Args:
            name: Folder visible name.
            parent_id: Optional parent folder UUID for nested folders, or empty string for root.
        """
        return app_editor.create_folder(name=name, parent_id=parent_id)

    @server.tool(
        name="move_document",
        description="Move a document or folder to another folder or back to root in the reMarkable library.",
    )
    def move_document(doc_id: str, parent_id: str = "") -> dict[str, Any]:
        """Move document or folder.

        Args:
            doc_id: UUID of document or folder to move.
            parent_id: Target folder UUID, or empty string "" for root library.
        """
        return app_editor.move_document(doc_id=doc_id, new_parent_id=parent_id)

    @server.tool(
        name="delete_document",
        description="Delete a document or folder (and all nested contents) from the reMarkable library.",
    )
    def delete_document(doc_id: str) -> dict[str, Any]:
        """Delete document or folder.

        Args:
            doc_id: UUID of document or folder to delete.
        """
        return app_editor.delete_document(doc_id=doc_id)

    return server
