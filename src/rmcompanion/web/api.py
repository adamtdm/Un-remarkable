"""REST API endpoints for reMarkable Companion."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel

from rmcompanion.cloud.auth import AuthManager
from rmcompanion.config import Settings
from rmcompanion.converter.engine import QUALITY_PROFILES, ConverterEngine
from rmcompanion.editor.notebook_editor import NotebookEditor
from rmcompanion.index.text_indexer import TextIndexer
from rmcompanion.intelligence.task_extractor import TaskExtractor
from rmcompanion.render.exporter import Exporter
from rmcompanion.store.blob_store import BlobStore
from rmcompanion.store.db import Database
from rmcompanion.sync.engine import SyncEngine

logger = logging.getLogger(__name__)


class RegisterCodeRequest(BaseModel):
    code: str


class ExcludeSearchRequest(BaseModel):
    exclude: bool


class ConvertDocRequest(BaseModel):
    quality_stop: int = 3
    split_spreads: bool = False
    manga_mode: bool = False


class TaskStatusRequest(BaseModel):
    status: str


class VisionSettingsRequest(BaseModel):
    provider: str = "gemini"
    api_key: str = ""
    model: str = "gemini-2.0-flash"
    base_url: str = ""


class CreateNotebookRequest(BaseModel):
    title: str
    initial_text: str = ""
    parent_id: str = ""


class UpdatePageTextRequest(BaseModel):
    text: str


class ImportMarkdownRequest(BaseModel):
    title: str
    markdown: str
    parent_id: str = ""


class ExportTasksNotebookRequest(BaseModel):
    notebook_title: str = "Tasks"


class CreateTaskItemRequest(BaseModel):
    text: str
    notebook_title: str = "Tasks"


class CreateFolderRequest(BaseModel):
    name: str
    parent_id: str = ""


class MoveDocumentRequest(BaseModel):
    parent_id: str = ""


def get_router(
    db: Database,
    blob_store: BlobStore,
    auth: AuthManager,
    sync_engine: SyncEngine,
    exporter: Exporter,
    converter_engine: ConverterEngine | None = None,
    text_indexer: TextIndexer | None = None,
    task_extractor: TaskExtractor | None = None,
    notebook_editor: NotebookEditor | None = None,
    settings: Settings | None = None,
) -> APIRouter:
    r = APIRouter(prefix="/api")
    editor = notebook_editor or NotebookEditor(db=db, blob_store=blob_store, task_extractor=task_extractor)

    @r.get("/status")
    async def get_status() -> dict[str, Any]:
        """System status, sync state, and auth status."""
        stats = blob_store.stats()
        return {
            "sync": sync_engine.status,
            "blobs_count": stats[0],
            "blobs_total_bytes": stats[1],
        }

    @r.post("/auth/register")
    async def register_device(payload: RegisterCodeRequest) -> dict[str, Any]:
        """Register device with an 8-character one-time code."""
        code = payload.code.strip()
        try:
            await auth.register_device(code)
            # Trigger immediate sync in background
            import asyncio
            asyncio.create_task(sync_engine.sync_once())
            return {"status": "ok", "message": "Device authenticated successfully"}
        except Exception as e:
            logger.error("Authentication failed: %s", e)
            raise HTTPException(status_code=400, detail=str(e))

    @r.post("/sync/trigger")
    async def trigger_sync() -> dict[str, Any]:
        """Manually trigger a sync cycle."""
        result = await sync_engine.sync_once()
        return result

    @r.get("/documents")
    def list_documents(
        parent_id: str = "",
        include_deleted: bool = False,
        file_type: str | None = None,
        type: str | None = None,
    ) -> list[dict[str, Any]]:
        """List documents in a given folder."""
        pid = parent_id if parent_id else ""
        effective_file_type = file_type or type
        return db.list_documents(parent_id=pid, include_deleted=include_deleted, file_type=effective_file_type)

    @r.get("/folders")
    def list_folders() -> list[dict[str, Any]]:
        """Get all folders in the library with hierarchical path and depth."""
        return db.get_folder_tree()

    @r.post("/folders")
    def create_folder(payload: CreateFolderRequest) -> dict[str, Any]:
        """Create a new folder in the library."""
        if not notebook_editor:
            raise HTTPException(status_code=503, detail="Notebook editor not available")
        try:
            folder = notebook_editor.create_folder(payload.name, payload.parent_id)
            return {"status": "ok", "folder": folder}
        except (ValueError, FileNotFoundError) as e:
            raise HTTPException(status_code=400, detail=str(e))

    @r.post("/documents/{doc_id}/move")
    def move_document(doc_id: str, payload: MoveDocumentRequest) -> dict[str, Any]:
        """Move a document or folder to a target parent folder (or root "")."""
        if not notebook_editor:
            raise HTTPException(status_code=503, detail="Notebook editor not available")
        try:
            res = notebook_editor.move_document(doc_id, payload.parent_id)
            return {"status": "ok", "result": res}
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @r.delete("/documents/{doc_id}")
    def delete_document(doc_id: str) -> dict[str, Any]:
        """Soft delete a document or folder (including all nested descendants)."""
        if not notebook_editor:
            raise HTTPException(status_code=503, detail="Notebook editor not available")
        try:
            res = notebook_editor.delete_document(doc_id)
            return {"status": "ok", "result": res}
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @r.get("/documents/{doc_id}")
    def get_document(doc_id: str) -> dict[str, Any]:
        """Get document metadata, pages, and version history."""
        doc = db.get_document(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        versions = db.list_versions(doc_id)
        doc["versions"] = versions
        return doc

    @r.post("/documents/{doc_id}/exclude-search")
    def set_exclude_search(doc_id: str, payload: ExcludeSearchRequest) -> dict[str, Any]:
        """Set search/OCR exclusion for a document or folder."""
        doc = db.get_document(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        affected = db.set_exclude_from_search(doc_id, payload.exclude)
        # If un-excluding, trigger re-indexing for all affected non-collection documents
        if not payload.exclude and text_indexer:
            for aff_id in affected:
                target_doc = db.get_document(aff_id)
                if (
                    target_doc
                    and not target_doc.get("deleted")
                    and target_doc.get("type") != "CollectionType"
                ):
                    try:
                        text_indexer.index_document(aff_id, target_doc.get("doc_hash", ""))
                    except Exception as e:
                        logger.warning("Failed to re-index %s: %s", aff_id, e)
        return {
            "ok": True,
            "doc_id": doc_id,
            "exclude_from_search": payload.exclude,
            "affected_count": len(affected),
        }

    @r.post("/documents/{doc_id}/indexing-toggle")
    def toggle_exclude_search(doc_id: str) -> dict[str, Any]:
        """Toggle current exclusion state for a document or folder."""
        doc = db.get_document(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        new_state = not doc.get("exclude_from_search", False)
        return set_exclude_search(doc_id, ExcludeSearchRequest(exclude=new_state))

    @r.get("/documents/{doc_id}/pages/{page_idx}/svg")
    def get_page_svg(doc_id: str, page_idx: int = 0, dark: bool = False) -> Response:
        """Render a single page to SVG."""
        try:
            svg = exporter.render_page_svg(doc_id, page_idx=page_idx, dark_mode=dark)
            return Response(
                content=svg,
                media_type="image/svg+xml",
                headers={"Cache-Control": "public, max-age=86400, stale-while-revalidate=604800"},
            )
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Document not found")
        except Exception as e:
            logger.exception("Error rendering page %d for %s: %s", page_idx, doc_id, e)
            raise HTTPException(status_code=500, detail=str(e))

    @r.get("/documents/{doc_id}/pages/{page_idx}/png")
    def get_page_png(doc_id: str, page_idx: int = 0, dark: bool = False) -> Response:
        """Render a single page to PNG."""
        try:
            png = exporter.render_page_png(doc_id, page_idx=page_idx, dark_mode=dark)
            return Response(
                content=png,
                media_type="image/png",
                headers={"Cache-Control": "public, max-age=86400, stale-while-revalidate=604800"},
            )
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Document not found")
        except Exception as e:
            logger.exception("Error rendering PNG for %s: %s", doc_id, e)
            raise HTTPException(status_code=500, detail=str(e))

    @r.get("/documents/{doc_id}/export/pdf")
    def export_pdf(doc_id: str, dark: bool = False) -> Response:
        """Download document as annotated PDF."""
        try:
            pdf_bytes = exporter.export_annotated_pdf(doc_id, dark_mode=dark)
            doc = db.get_document(doc_id)
            title = doc["visible_name"] if doc else "document"
            clean_title = "".join(c for c in title if c.isalnum() or c in " ._-").strip() or "document"
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{clean_title}.pdf"'},
            )
        except Exception as e:
            logger.exception("Error exporting PDF for %s: %s", doc_id, e)
            raise HTTPException(status_code=500, detail=str(e))

    # --- Converter Endpoints ---

    @r.get("/converter/profiles")
    def get_converter_profiles() -> list[dict[str, Any]]:
        """List available quality slider profiles."""
        return [
            {
                "stop": p.stop,
                "name": p.name,
                "max_width": p.max_width,
                "max_height": p.max_height,
                "jpeg_quality": p.jpeg_quality,
                "description": p.description,
            }
            for p in QUALITY_PROFILES.values()
        ]

    @r.post("/documents/{doc_id}/convert")
    async def convert_library_doc(doc_id: str, payload: ConvertDocRequest) -> dict[str, Any]:
        """Start optimization job for an existing document in the library."""
        if not converter_engine:
            raise HTTPException(status_code=503, detail="Converter engine not initialized")
        try:
            job_id = await converter_engine.start_job_from_doc(
                doc_id=doc_id,
                quality_stop=payload.quality_stop,
                split_spreads=payload.split_spreads,
                manga_mode=payload.manga_mode,
            )
            return {"ok": True, "job_id": job_id}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.exception("Failed to start convert job for %s: %s", doc_id, e)
            raise HTTPException(status_code=500, detail=str(e))

    @r.post("/converter/upload")
    async def convert_upload(
        file: UploadFile = File(...),
        quality_stop: int = Form(3),
        split_spreads: bool = Form(False),
        manga_mode: bool = Form(False),
    ) -> dict[str, Any]:
        """Upload and convert an external file (PDF, EPUB, CBZ)."""
        if not converter_engine:
            raise HTTPException(status_code=503, detail="Converter engine not initialized")
        try:
            file_bytes = await file.read()
            job_id = await converter_engine.start_job_from_upload(
                filename=file.filename or "upload.pdf",
                input_bytes=file_bytes,
                quality_stop=quality_stop,
                split_spreads=split_spreads,
                manga_mode=manga_mode,
            )
            return {"ok": True, "job_id": job_id}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.exception("Failed to convert uploaded file: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    @r.get("/converter/jobs")
    def list_converter_jobs() -> list[dict[str, Any]]:
        """List active and recent conversion jobs."""
        if not converter_engine:
            return []
        return converter_engine.list_jobs()

    @r.get("/converter/jobs/{job_id}")
    def get_converter_job(job_id: str) -> dict[str, Any]:
        """Get status and progress of a conversion job."""
        if not converter_engine:
            raise HTTPException(status_code=503, detail="Converter engine not initialized")
        job = converter_engine.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    @r.get("/converter/jobs/{job_id}/download")
    def download_converted_file(job_id: str) -> Response:
        """Download the resulting optimized PDF."""
        if not converter_engine:
            raise HTTPException(status_code=503, detail="Converter engine not initialized")
        job = converter_engine.get_job(job_id)
        if not job or job.get("status") != "done":
            raise HTTPException(status_code=404, detail="Converted file not ready or not found")
        path = Path(job["output_path"])
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Output file missing from disk")

        pdf_bytes = path.read_bytes()
        filename = job.get("output_filename", "optimized.pdf")
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # --- Search & History ---

    @r.get("/search")
    def search(
        q: str = Query(..., min_length=1),
        limit: int = 25,
        only_notes: bool = False,
        include_excluded: bool = False,
    ) -> list[dict[str, Any]]:
        """Full-text search across documents and notes."""
        return db.search(
            query=q,
            limit=limit,
            only_notes=only_notes,
            include_excluded=include_excluded,
        )

    @r.get("/snapshots")
    def list_snapshots(limit: int = 30) -> list[dict[str, Any]]:
        """List historical sync snapshots."""
        return db.list_snapshots(limit=limit)

    # --- Tasks & Vision OCR ---

    @r.get("/tasks")
    def list_tasks(status: str | None = None, doc_id: str | None = None) -> list[dict[str, Any]]:
        """List tasks extracted from notebooks and handwritten notes."""
        return db.list_tasks(status=status, doc_id=doc_id)

    @r.post("/tasks/{task_id}/status")
    def update_task_status(task_id: str, payload: TaskStatusRequest) -> dict[str, Any]:
        """Update task completion status."""
        ok = db.set_task_status(task_id, payload.status)
        if not ok:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"ok": True, "task_id": task_id, "status": payload.status}

    @r.delete("/tasks/{task_id}")
    def delete_task(task_id: str) -> dict[str, Any]:
        """Delete an extracted task."""
        ok = db.delete_task(task_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"ok": True, "task_id": task_id}

    @r.post("/tasks/scan/{doc_id}")
    async def scan_doc_tasks(doc_id: str) -> dict[str, Any]:
        """Trigger task extraction for a single document."""
        if not task_extractor:
            raise HTTPException(status_code=503, detail="Task extractor not initialized")
        tasks = await task_extractor.scan_document_for_tasks(doc_id)
        return {"ok": True, "doc_id": doc_id, "tasks_found": len(tasks), "tasks": tasks}

    @r.post("/tasks/scan-all")
    async def scan_all_tasks() -> dict[str, Any]:
        """Scan all non-excluded documents for to-do items and tasks."""
        if not task_extractor:
            raise HTTPException(status_code=503, detail="Task extractor not initialized")
        docs = db.list_documents()
        total_found = 0
        for doc in docs:
            if doc.get("type") != "CollectionType" and not doc.get("deleted") and not doc.get("exclude_from_search"):
                tasks = await task_extractor.scan_document_for_tasks(doc["id"])
                total_found += len(tasks)
        return {"ok": True, "tasks_found": total_found}

    @r.get("/settings/vision")
    def get_vision_settings() -> dict[str, Any]:
        """Get vision provider settings (API key masked)."""
        raw = db.get_state("vision_settings", "")
        if not raw:
            return {
                "provider": "gemini",
                "model": "gemini-2.0-flash",
                "api_key_set": False,
                "api_key_masked": "",
                "base_url": "",
            }
        try:
            conf = json.loads(raw)
        except Exception:
            conf = {}
        key = conf.get("api_key", "")
        masked = f"{key[:4]}...{key[-4:]}" if len(key) > 8 else ("****" if key else "")
        return {
            "provider": conf.get("provider", "gemini"),
            "model": conf.get("model", "gemini-2.0-flash"),
            "api_key_set": bool(key),
            "api_key_masked": masked,
            "base_url": conf.get("base_url", ""),
        }

    @r.post("/settings/vision")
    def save_vision_settings(payload: VisionSettingsRequest) -> dict[str, Any]:
        """Save vision provider settings."""
        curr_raw = db.get_state("vision_settings", "")
        existing_key = ""
        if curr_raw:
            try:
                existing_key = json.loads(curr_raw).get("api_key", "")
            except Exception:
                pass

        final_key = payload.api_key.strip() if payload.api_key.strip() else existing_key
        conf = {
            "provider": payload.provider.lower(),
            "api_key": final_key,
            "model": payload.model.strip(),
            "base_url": payload.base_url.strip(),
        }
        db.set_state("vision_settings", json.dumps(conf))

        if task_extractor:
            from rmcompanion.intelligence.provider import get_vision_provider
            task_extractor.vision_provider = get_vision_provider(db)

        return {"ok": True, "provider": conf["provider"], "model": conf["model"]}

    @r.post("/settings/vision/test")
    async def test_vision_settings(payload: VisionSettingsRequest) -> dict[str, Any]:
        """Test API key and latency for vision provider."""
        from rmcompanion.intelligence.provider import VisionProvider
        provider = VisionProvider(
            provider=payload.provider,
            api_key=payload.api_key,
            model=payload.model,
            base_url=payload.base_url,
        )
        try:
            return await provider.test_connection()
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    # Phase 4: Typed notebook editor and markdown import endpoints
    @r.post("/documents/new")
    def create_notebook_endpoint(payload: CreateNotebookRequest) -> dict[str, Any]:
        """Create a new native reMarkable notebook."""
        title = payload.title.strip() or "Untitled Notebook"
        try:
            return editor.create_notebook(
                title=title,
                initial_text=payload.initial_text,
                parent_id=payload.parent_id,
            )
        except Exception as e:
            logger.error("Failed to create notebook: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    @r.get("/documents/{doc_id}/pages/{page_idx}/text")
    def get_page_text_endpoint(doc_id: str, page_idx: int) -> dict[str, Any]:
        """Get typed text of a notebook page."""
        try:
            text = editor.get_page_typed_text(doc_id, page_idx)
            return {"doc_id": doc_id, "page_idx": page_idx, "text": text}
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Document not found")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @r.put("/documents/{doc_id}/pages/{page_idx}/text")
    def update_page_text_endpoint(
        doc_id: str,
        page_idx: int,
        payload: UpdatePageTextRequest,
    ) -> dict[str, Any]:
        """Update typed text of a notebook page."""
        try:
            res = editor.update_page_typed_text(doc_id, page_idx, payload.text)
            return {"ok": True, "result": res}
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Document not found")
        except IndexError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error("Failed to update page text: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    @r.post("/documents/import-markdown")
    def import_markdown_endpoint(payload: ImportMarkdownRequest) -> dict[str, Any]:
        """Import markdown content to a new notebook."""
        title = payload.title.strip() or "Imported Note"
        try:
            return editor.import_markdown(
                title=title,
                markdown_content=payload.markdown,
                parent_id=payload.parent_id,
            )
        except Exception as e:
            logger.error("Failed to import markdown: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    @r.post("/tasks/export-to-notebook")
    def export_tasks_to_notebook_endpoint(payload: ExportTasksNotebookRequest) -> dict[str, Any]:
        """Consolidate open tasks into the synced Tasks notebook."""
        try:
            res = editor.sync_tasks_to_notebook(payload.notebook_title)
            return {"ok": True, "result": res}
        except Exception as e:
            logger.error("Failed to export tasks to notebook: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    @r.post("/tasks/create-item")
    def create_task_item_endpoint(payload: CreateTaskItemRequest) -> dict[str, Any]:
        """Append a single task checkbox to the Tasks notebook."""
        if not payload.text.strip():
            raise HTTPException(status_code=400, detail="Task text cannot be empty")
        try:
            res = editor.append_task_to_tasks_notebook(payload.text, payload.notebook_title)
            return {"ok": True, "result": res}
        except Exception as e:
            logger.error("Failed to append task item: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    return r
