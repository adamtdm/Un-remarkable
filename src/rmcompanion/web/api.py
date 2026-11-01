"""REST API endpoints for reMarkable Companion."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import zipfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, Response, UploadFile
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
    device: str = "paper_pro"


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


class QuickCaptureRequest(BaseModel):
    text: str
    is_task: bool = True
    notebook_title: str = ""


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

    def _push_bg(coro: Any) -> None:
        if sync_engine and sync_engine.auth.tokens.is_authenticated:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(coro)
            except RuntimeError:
                try:
                    asyncio.run_coroutine_threadsafe(coro, asyncio.get_event_loop())
                except Exception:
                    coro.close()
        else:
            coro.close()

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

    @r.post("/auth/logout")
    async def logout_device() -> dict[str, Any]:
        """Unlink tablet and clear auth tokens."""
        auth.clear_tokens()
        return {"status": "ok", "message": "Successfully unlinked device from reMarkable Cloud"}

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
        folders = db.get_folder_tree()
        for f in folders:
            f["name"] = f.get("visible_name", "")
        return folders

    @r.post("/folders")
    async def create_folder(payload: CreateFolderRequest) -> dict[str, Any]:
        """Create a new folder in the library and push to reMarkable Cloud."""
        if not notebook_editor:
            raise HTTPException(status_code=503, detail="Notebook editor not available")
        try:
            folder = notebook_editor.create_folder(payload.name, payload.parent_id)
            _push_bg(sync_engine.create_remote_folder(folder["id"], payload.name, payload.parent_id))
            return {"status": "ok", "folder": folder}
        except (ValueError, FileNotFoundError) as e:
            raise HTTPException(status_code=400, detail=str(e))

    @r.post("/documents/{doc_id}/move")
    async def move_document(doc_id: str, payload: MoveDocumentRequest) -> dict[str, Any]:
        """Move a document or folder to a target parent folder (or root "")."""
        if not notebook_editor:
            raise HTTPException(status_code=503, detail="Notebook editor not available")
        try:
            res = notebook_editor.move_document(doc_id, payload.parent_id)
            _push_bg(sync_engine.move_remote_document(doc_id, payload.parent_id))
            return {"status": "ok", "result": res}
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @r.delete("/documents/{doc_id}")
    async def delete_document(doc_id: str) -> dict[str, Any]:
        """Soft delete a document or folder and remove from reMarkable Cloud."""
        if not notebook_editor:
            raise HTTPException(status_code=503, detail="Notebook editor not available")
        try:
            res = notebook_editor.delete_document(doc_id)
            _push_bg(sync_engine.delete_remote_document(doc_id))
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

    @r.api_route("/documents/{doc_id}/thumbnail", methods=["GET", "HEAD"])
    def get_document_thumbnail(
        doc_id: str,
        dark: bool = False,
        request: Request = None,
    ) -> Response:
        """Fast, lightweight thumbnail for document cards with ETag caching."""
        doc = db.get_document(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        doc_hash = doc.get("doc_hash", "")
        etag = f'"{doc_hash}_v2"'

        if request:
            if_none_match = request.headers.get("if-none-match")
            if if_none_match and if_none_match == etag:
                return Response(
                    status_code=304,
                    headers={
                        "ETag": etag,
                        "Cache-Control": "public, max-age=604800, immutable",
                    },
                )

        try:
            png_bytes = exporter.render_thumbnail(doc_id, dark_mode=False)
            content = b"" if (request and request.method == "HEAD") else png_bytes
            return Response(
                content=content,
                media_type="image/png",
                headers={
                    "ETag": etag,
                    "Cache-Control": "public, max-age=604800, immutable",
                    "Content-Length": str(len(png_bytes)),
                },
            )
        except Exception as e:
            logger.warning("Failed to render thumbnail for %s: %s", doc_id, e)
            raise HTTPException(status_code=500, detail=str(e))

    @r.post("/thumbnails/clear-cache")
    def clear_thumbnails() -> dict[str, Any]:
        """Purge disk thumbnail cache to regenerate covers cleanly."""
        deleted = exporter.clear_thumbnail_cache()
        return {"ok": True, "deleted_count": deleted}

    @r.api_route("/documents/{doc_id}/pages/{page_idx}/svg", methods=["GET", "HEAD"])
    def get_page_svg(doc_id: str, page_idx: int = 0, dark: bool = False, request: Request = None) -> Response:
        """Render a single page to SVG."""
        try:
            svg = exporter.render_page_svg(doc_id, page_idx=page_idx, dark_mode=dark)
            content = "" if (request and request.method == "HEAD") else svg
            return Response(
                content=content,
                media_type="image/svg+xml",
                headers={
                    "Cache-Control": "public, max-age=86400, stale-while-revalidate=604800",
                    "Content-Length": str(len(svg.encode("utf-8"))),
                },
            )
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Document not found")
        except Exception as e:
            logger.exception("Error rendering page %d for %s: %s", page_idx, doc_id, e)
            raise HTTPException(status_code=500, detail=str(e))

    @r.api_route("/documents/{doc_id}/pages/{page_idx}/png", methods=["GET", "HEAD"])
    def get_page_png(doc_id: str, page_idx: int = 0, dark: bool = False, request: Request = None) -> Response:
        """Render a single page to PNG."""
        try:
            png = exporter.render_page_png(doc_id, page_idx=page_idx, dark_mode=dark)
            content = b"" if (request and request.method == "HEAD") else png
            return Response(
                content=content,
                media_type="image/png",
                headers={
                    "Cache-Control": "public, max-age=86400, stale-while-revalidate=604800",
                    "Content-Length": str(len(png)),
                },
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

    @r.get("/documents/{doc_id}/export/zip")
    def export_folder_zip(doc_id: str) -> Response:
        """Download a folder or notebook hierarchy as a ZIP archive."""
        root_doc = db.get_document(doc_id)
        if not root_doc:
            raise HTTPException(status_code=404, detail="Document or folder not found")

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            def _add_to_zip(d: dict[str, Any], prefix: str) -> None:
                name = d.get("visible_name", "document")
                clean_name = "".join(c for c in name if c.isalnum() or c in " ._-").strip() or "item"
                if d.get("type") == "CollectionType":
                    folder_prefix = f"{prefix}{clean_name}/"
                    children = db.list_documents(parent_id=d["id"])
                    if not children:
                        zf.writestr(folder_prefix, "")
                    for child in children:
                        _add_to_zip(child, folder_prefix)
                else:
                    # Check for direct PDF or EPUB blob first for instant archival export
                    doc_files = db.get_document_files(d["id"])
                    pdf_file = next((df for df in doc_files if df.get("file_id", "").endswith(".pdf")), None)
                    epub_file = next((df for df in doc_files if df.get("file_id", "").endswith(".epub")), None)

                    if pdf_file and blob_store.has(pdf_file["blob_hash"]):
                        p = blob_store.get_path(pdf_file["blob_hash"])
                        if p and p.is_file():
                            zf.write(p, arcname=f"{prefix}{clean_name}.pdf")
                            return
                    elif epub_file and blob_store.has(epub_file["blob_hash"]):
                        p = blob_store.get_path(epub_file["blob_hash"])
                        if p and p.is_file():
                            zf.write(p, arcname=f"{prefix}{clean_name}.epub")
                            return

                    # Handwritten notebook or document needing vector stroke rendering
                    try:
                        pdf_bytes = exporter.export_annotated_pdf(d["id"])
                        zf.writestr(f"{prefix}{clean_name}.pdf", pdf_bytes)
                    except Exception as err:
                        logger.warning("Could not render PDF for %s: %s", d["id"], err)
                        for df in doc_files:
                            p = blob_store.get_path(df["blob_hash"])
                            if p and p.is_file():
                                zf.write(p, arcname=f"{prefix}{clean_name}_{df['file_id']}")

            if root_doc.get("type") == "CollectionType":
                children = db.list_documents(parent_id=root_doc["id"])
                for child in children:
                    _add_to_zip(child, "")
            else:
                _add_to_zip(root_doc, "")

        zip_buf.seek(0)
        zip_name = "".join(c for c in root_doc.get("visible_name", "export") if c.isalnum() or c in " ._-").strip() or "archive"
        return Response(
            content=zip_buf.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{zip_name}.zip"'},
        )

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
                device=payload.device,
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
        device: str = Form("paper_pro"),
        parent_id: str = Form(""),
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
                device=device,
                parent_id=parent_id,
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

    @r.post("/settings/vision/models")
    async def list_vision_models(payload: VisionSettingsRequest) -> dict[str, Any]:
        """Query available vision models for the provider and API key, defaulting to newest."""
        provider = (payload.provider or "gemini").lower()
        api_key = payload.api_key.strip()
        base_url = payload.base_url.strip()

        # If key is empty in request, check if we have a saved key in database
        if not api_key:
            raw = db.get_state("vision_settings", "")
            if raw:
                try:
                    saved = json.loads(raw)
                    if saved.get("provider") == provider:
                        api_key = saved.get("api_key", "")
                        if not base_url:
                            base_url = saved.get("base_url", "")
                except Exception:
                    pass

        models: list[dict[str, Any]] = []
        default_model = "gemini-2.0-flash" if provider == "gemini" else "gpt-4o-mini"

        if provider == "gemini":
            if api_key:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
                    async with httpx.AsyncClient(timeout=4.0) as client:
                        resp = await client.get(url)
                        if resp.status_code == 200:
                            data = resp.json()
                            raw_models = data.get("models", [])
                            found_ids = []
                            for m in raw_models:
                                mid = m.get("name", "").replace("models/", "")
                                if "gemini" in mid and "vision" not in mid and not mid.endswith("-latest"):
                                    methods = m.get("supportedGenerationMethods", [])
                                    if "generateContent" in methods:
                                        found_ids.append(mid)

                            priority = [
                                "gemini-2.5-pro",
                                "gemini-2.0-flash",
                                "gemini-2.0-flash-lite",
                                "gemini-1.5-flash",
                                "gemini-1.5-pro",
                            ]
                            seen = set()
                            for p in priority:
                                for f in found_ids:
                                    if f.startswith(p) and f not in seen:
                                        seen.add(f)
                                        desc = "Newest — Fast & Accurate" if p == "gemini-2.0-flash" else ("Lightweight & Economical" if "lite" in p else "High Capability")
                                        models.append({"id": f, "name": f"{f} ({desc})", "is_recommended": (f == "gemini-2.0-flash")})

                            if not any(m["is_recommended"] for m in models) and models:
                                models[0]["is_recommended"] = True
                except Exception as e:
                    logger.debug("Failed to query Gemini API for live models: %s", e)

            if not models:
                models = [
                    {"id": "gemini-2.0-flash", "name": "gemini-2.0-flash (Newest Recommended — Fast & High Accuracy)", "is_recommended": True},
                    {"id": "gemini-2.0-flash-lite", "name": "gemini-2.0-flash-lite (Cost Effective & Lightweight)", "is_recommended": False},
                    {"id": "gemini-1.5-flash", "name": "gemini-1.5-flash (Standard Balanced)", "is_recommended": False},
                    {"id": "gemini-1.5-pro", "name": "gemini-1.5-pro (High Reasoning)", "is_recommended": False},
                ]
            default_model = "gemini-2.0-flash"

        elif provider == "openai":
            if base_url:
                try:
                    url = f"{base_url.rstrip('/')}/v1/models"
                    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                    async with httpx.AsyncClient(timeout=3.0) as client:
                        resp = await client.get(url, headers=headers)
                        if resp.status_code == 200:
                            data = resp.json()
                            for m in data.get("data", []):
                                mid = m.get("id", "")
                                if mid:
                                    models.append({"id": mid, "name": mid, "is_recommended": False})
                except Exception:
                    pass

            if not models:
                models = [
                    {"id": "gpt-4o-mini", "name": "gpt-4o-mini (Newest Recommended — Fast Vision)", "is_recommended": True},
                    {"id": "gpt-4o", "name": "gpt-4o (Omni Multimodal)", "is_recommended": False},
                    {"id": "llama3.2-vision", "name": "llama3.2-vision (Local Ollama Vision)", "is_recommended": False},
                    {"id": "llava", "name": "llava (Local Ollama Vision)", "is_recommended": False},
                    {"id": "qwen2.5-vl", "name": "qwen2.5-vl (Local Ollama Vision)", "is_recommended": False},
                ]
            default_model = "gpt-4o-mini"

        return {
            "ok": True,
            "provider": provider,
            "models": models,
            "default_model": default_model,
        }

    @r.post("/settings/rescan")
    async def rescan_library() -> dict[str, Any]:
        """Rescan and re-index all documents in the library, strictly respecting excluded folders and documents."""
        docs = db.list_documents(include_deleted=False)
        excluded_ids = db.get_all_excluded_ids()

        rescanned_count = 0
        excluded_count = 0
        tasks_count = 0

        # Purge search index and tasks for any documents that are in excluded_ids
        if excluded_ids:
            placeholders = ",".join("?" for _ in excluded_ids)
            with db.connect() as conn:
                conn.execute(
                    f"DELETE FROM search_index WHERE doc_id IN ({placeholders}) AND source NOT IN ('title')",
                    list(excluded_ids),
                )
                conn.execute(
                    f"DELETE FROM tasks WHERE doc_id IN ({placeholders})",
                    list(excluded_ids),
                )

        for d in docs:
            doc_id = d["id"]
            if d.get("type") == "CollectionType":
                continue

            if doc_id in excluded_ids or d.get("exclude_from_search"):
                excluded_count += 1
                continue

            doc_hash = d.get("doc_hash", "")
            # Re-index text and handwriting OCR
            if text_indexer:
                try:
                    await asyncio.to_thread(text_indexer.index_document, doc_id, doc_hash)
                except Exception as e:
                    logger.warning("Error re-indexing %s during rescan: %s", doc_id, e)

            # Warm thumbnail in authentic colors
            if exporter:
                try:
                    await asyncio.to_thread(exporter.warm_thumbnail, doc_id, doc_hash)
                except Exception as e:
                    logger.debug("Failed warming thumbnail for %s: %s", doc_id, e)

            # Re-extract tasks
            if task_extractor:
                try:
                    found = await task_extractor.scan_document_for_tasks(doc_id)
                    tasks_count += len(found)
                except Exception as e:
                    logger.warning("Error scanning tasks for %s: %s", doc_id, e)

            rescanned_count += 1
            await asyncio.sleep(0)

        return {
            "ok": True,
            "total_documents": len([d for d in docs if d.get("type") != "CollectionType"]),
            "rescanned_count": rescanned_count,
            "excluded_count": excluded_count,
            "tasks_found": tasks_count,
            "message": f"Rescan complete: {rescanned_count} documents indexed, {excluded_count} excluded documents skipped, {tasks_count} tasks found.",
        }

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
    async def update_page_text_endpoint(
        doc_id: str,
        page_idx: int,
        payload: UpdatePageTextRequest,
    ) -> dict[str, Any]:
        """Update typed text of a notebook page and push to cloud."""
        try:
            res = editor.update_page_typed_text(doc_id, page_idx, payload.text)
            target_doc = db.get_document(doc_id)
            if target_doc:
                try:
                    pdf_bytes = exporter.export_annotated_pdf(doc_id)
                    title = target_doc.get("visible_name", "document")
                    pid = "" if title.strip().lower() == "tasks" else target_doc.get("parent_id", "")
                    _push_bg(sync_engine.push_document(pdf_bytes, title, parent_id=pid))
                except Exception as ex:
                    logger.warning("Failed to queue document PDF push to cloud: %s", ex)
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
    async def export_tasks_to_notebook_endpoint(payload: ExportTasksNotebookRequest) -> dict[str, Any]:
        """Consolidate open tasks into the synced Tasks notebook and push to cloud."""
        try:
            res = editor.sync_tasks_to_notebook(payload.notebook_title)
            doc_id = res["id"]
            try:
                pdf_bytes = exporter.export_annotated_pdf(doc_id)
                _push_bg(sync_engine.push_document(pdf_bytes, payload.notebook_title, parent_id=""))
            except Exception as ex:
                logger.warning("Failed to queue Tasks PDF push to cloud: %s", ex)
            return {"ok": True, "result": res}
        except Exception as e:
            logger.error("Failed to export tasks to notebook: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    @r.post("/tasks/create-item")
    async def create_task_item_endpoint(payload: CreateTaskItemRequest) -> dict[str, Any]:
        """Append a single task checkbox to the Tasks notebook and push to cloud."""
        if not payload.text.strip():
            raise HTTPException(status_code=400, detail="Task text cannot be empty")
        try:
            res = editor.append_task_to_tasks_notebook(payload.text, payload.notebook_title)
            doc_id = res["id"]
            try:
                pdf_bytes = exporter.export_annotated_pdf(doc_id)
                _push_bg(sync_engine.push_document(pdf_bytes, payload.notebook_title, parent_id=""))
            except Exception as ex:
                logger.warning("Failed to queue Tasks PDF push to cloud: %s", ex)
            return {"ok": True, "result": res}
        except Exception as e:
            logger.error("Failed to append task item: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    @r.post("/notes/quick-capture")
    async def quick_capture_endpoint(payload: QuickCaptureRequest) -> dict[str, Any]:
        """Instantly capture a task or quick note entry into a synchronized notebook and push to cloud."""
        text = payload.text.strip()
        if not text:
            raise HTTPException(status_code=400, detail="Capture text cannot be empty")
        try:
            if payload.is_task:
                target_title = payload.notebook_title or "Tasks"
                res = editor.append_task_to_tasks_notebook(text, target_title)
                try:
                    pdf_bytes = exporter.export_annotated_pdf(res["id"])
                    _push_bg(sync_engine.push_document(pdf_bytes, target_title, parent_id=""))
                except Exception as ex:
                    logger.warning("Failed to queue Tasks PDF push to cloud: %s", ex)
            else:
                target_title = payload.notebook_title or "Quick Notes"
                res = editor.append_note_to_notebook(text, target_title)
                try:
                    pdf_bytes = exporter.export_annotated_pdf(res["id"])
                    _push_bg(sync_engine.push_document(pdf_bytes, target_title, parent_id=""))
                except Exception as ex:
                    logger.warning("Failed to queue Quick Notes PDF push to cloud: %s", ex)
            return {"ok": True, "result": res}
        except Exception as e:
            logger.error("Failed to process quick capture: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    @r.post("/documents/bulk-import")
    async def bulk_import_documents(
        files: list[UploadFile] = File(...),
        device: str = Form("none"),
        parent_id: str = Form(""),
        quality_stop: int = Form(3),
    ) -> dict[str, Any]:
        """Bulk import documents (PDF, EPUB, Markdown, Text) with optional device optimization and cloud sync."""
        imported: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []

        for upload in files:
            orig_name = upload.filename or "uploaded_file"
            stem = Path(orig_name).stem
            ext = Path(orig_name).suffix.lstrip(".").lower()
            try:
                content = await upload.read()
                if not content:
                    errors.append({"file": orig_name, "error": "File is empty"})
                    continue

                if device in {"paper_pro", "rm2", "rm1"} and ext in {"pdf", "epub", "cbz"} and converter_engine:
                    opt_pdf = await asyncio.to_thread(
                        converter_engine.convert_sync,
                        input_source=content,
                        input_type=ext,
                        quality_stop=quality_stop,
                        device=device,
                    )
                    res = await asyncio.to_thread(editor.import_pdf_file, title=stem, pdf_bytes=opt_pdf, parent_id=parent_id)
                    imported.append({"file": orig_name, "id": res["id"], "type": "pdf", "optimized": True})
                    _push_bg(sync_engine.push_document(opt_pdf, filename=stem, parent_id=parent_id, file_type="pdf"))
                elif ext == "pdf":
                    res = await asyncio.to_thread(editor.import_pdf_file, title=stem, pdf_bytes=content, parent_id=parent_id)
                    imported.append({"file": orig_name, "id": res["id"], "type": "pdf", "optimized": False})
                    _push_bg(sync_engine.push_document(content, filename=stem, parent_id=parent_id, file_type="pdf"))
                elif ext == "epub":
                    res = await asyncio.to_thread(editor.import_epub_file, title=stem, epub_bytes=content, parent_id=parent_id)
                    imported.append({"file": orig_name, "id": res["id"], "type": "epub", "optimized": False})
                    _push_bg(sync_engine.push_document(content, filename=stem, parent_id=parent_id, file_type="epub"))
                elif ext in {"md", "markdown", "txt"}:
                    text_str = content.decode("utf-8", errors="replace")
                    res = await asyncio.to_thread(editor.import_markdown, title=stem, markdown_content=text_str, parent_id=parent_id)
                    imported.append({"file": orig_name, "id": res["id"], "type": "notebook", "optimized": False})
                    try:
                        pdf_bytes = exporter.export_annotated_pdf(res["id"])
                        _push_bg(sync_engine.push_document(pdf_bytes, filename=stem, parent_id=parent_id, file_type="pdf"))
                    except Exception as e:
                        logger.debug("Could not export imported note %s to PDF: %s", stem, e)
                else:
                    errors.append({"file": orig_name, "error": f"Unsupported file type .{ext}"})
            except Exception as e:
                logger.exception("Failed to import file %s: %s", orig_name, e)
                errors.append({"file": orig_name, "error": str(e)})

        return {
            "ok": len(imported) > 0,
            "imported_count": len(imported),
            "imported": imported,
            "errors": errors,
        }

    return r
