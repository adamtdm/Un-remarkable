"""REST API endpoints for reMarkable Companion."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import os
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any

import httpx
from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask

from rmcompanion.cloud.auth import AuthManager
from rmcompanion.config import Settings
from rmcompanion.converter.engine import QUALITY_PROFILES, ConverterEngine
from rmcompanion.delivery.manager import DeliveryManager
from rmcompanion.delivery.models import DeliverySettings
from rmcompanion.delivery.rss_directory import (
    CATEGORIES,
    POPULAR_FEEDS,
    PRESETS,
    discover_feed_url,
    search_popular_feeds,
    validate_feed,
)
from rmcompanion.editor.notebook_editor import NotebookEditor
from rmcompanion.index.text_indexer import TextIndexer
from rmcompanion.intelligence.task_extractor import TaskExtractor
from rmcompanion.reading import (
    document_highlights,
    highlights_markdown,
    table_of_contents,
)
from rmcompanion.render.exporter import Exporter
from rmcompanion.store.blob_store import BlobStore
from rmcompanion.store.db import Database
from rmcompanion.sync.engine import SyncEngine

logger = logging.getLogger(__name__)

_LIVE_MODELS_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}


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
    model: str = "gemini-flash-lite-latest"
    base_url: str = ""


class CreateNotebookRequest(BaseModel):
    title: str
    initial_text: str = ""
    parent_id: str = ""


class FeedValidateRequest(BaseModel):
    url: str


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


class DocumentViewRequest(BaseModel):
    two_page: bool | None = None
    rtl: bool | None = None
    cover_alone: bool | None = None
    bookmarks: list[int] | None = None


class UpdatePositionRequest(BaseModel):
    page_idx: int


def _safe_name(name: str, fallback: str) -> str:
    """Strip a document title down to characters safe for file names and headers."""
    return "".join(c for c in name if c.isalnum() or c in " ._-").strip() or fallback


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
    delivery_manager: DeliveryManager | None = None,
) -> APIRouter:
    r = APIRouter(prefix="/api")
    editor = notebook_editor or NotebookEditor(db=db, blob_store=blob_store, task_extractor=task_extractor)
    dm = delivery_manager or DeliveryManager(
        db=db,
        client=sync_engine.client,
        sync_engine=sync_engine,
        notebook_editor=editor,
    )

    def _markdown_download(md: str, name: str) -> Response:
        return Response(
            content=md,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{_safe_name(name, "highlights")}.md"'},
        )

    @r.get("/status")
    async def get_status() -> dict[str, Any]:
        """System status, sync state, and auth status. Polled by the Docker healthcheck, so keep it cheap."""
        return {"sync": sync_engine.status}

    @r.post("/auth/register")
    async def register_device(payload: RegisterCodeRequest) -> dict[str, Any]:
        """Register device with an 8-character one-time code."""
        code = payload.code.strip()
        try:
            await auth.register_device(code)
            # Trigger immediate sync in background
            sync_engine.spawn(sync_engine.sync_once())
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

    @r.get("/documents/continue-reading")
    def continue_reading(limit: int = 10) -> dict[str, Any]:
        """Books and comics most recently opened (on the tablet or here), for the Continue Reading shelf."""
        books = [
            d for d in db.list_documents(include_deleted=False)
            if d.get("type") == "DocumentType" and d.get("file_type") in ("pdf", "epub")
            and d.get("parent_id") != "trash" and str(d.get("last_opened") or "0").isdigit()
            and int(d.get("last_opened") or 0) > 0
            # Unfinished, and long enough to be "reading" (not a one-page crossword).
            and (d.get("page_count") or 0) > 2 and (d.get("last_opened_page") or 0) < d["page_count"] - 1
        ]
        books.sort(key=lambda d: int(d["last_opened"]), reverse=True)
        return {"documents": books[: max(1, min(limit, 50))]}

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
            sync_engine.spawn(sync_engine.create_remote_folder(folder["id"], payload.name, payload.parent_id))
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
            sync_engine.spawn(sync_engine.move_remote_document(doc_id, payload.parent_id))
            return {"status": "ok", "result": res}
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @r.delete("/documents/{doc_id}")
    async def delete_document(doc_id: str) -> dict[str, Any]:
        """Soft delete a document or folder and remove from reMarkable Cloud."""
        if not editor:
            raise HTTPException(status_code=503, detail="Notebook editor not available")
        try:
            res = editor.delete_document(doc_id)
            sync_engine.spawn(sync_engine.delete_remote_document(doc_id))
            return {"status": "ok", "result": res}
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @r.post("/documents/{doc_id}/position")
    async def update_document_position(doc_id: str, payload: UpdatePositionRequest) -> dict[str, Any]:
        """Update last read page position for a document and push to reMarkable Cloud."""
        try:
            res = editor.update_document_position(doc_id, payload.page_idx)
            sync_engine.spawn(sync_engine.update_remote_position(doc_id, payload.page_idx))
            return {"status": "ok", "result": res}
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error("Failed to update position for %s: %s", doc_id, e)
            raise HTTPException(status_code=500, detail=str(e))

    @r.get("/documents/{doc_id}")
    def get_document(doc_id: str) -> dict[str, Any]:
        """Get document metadata, pages, and version history."""
        doc = db.get_document(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        versions = db.list_versions(doc_id)
        doc["versions"] = versions
        doc.update(db.get_view_prefs(doc_id))
        return doc

    @r.post("/documents/{doc_id}/view")
    def set_document_view(doc_id: str, payload: DocumentViewRequest) -> dict[str, Any]:
        """Remember the web reader's choices for this document: spreads, reading direction, bookmarks."""
        if not db.get_document(doc_id):
            raise HTTPException(status_code=404, detail="Document not found")
        return {"ok": True, **db.set_view_prefs(doc_id, **payload.model_dump(exclude_none=True))}

    def _toc(doc: dict[str, Any]) -> list[dict[str, Any]]:
        source = next((f["blob_hash"] for f in doc.get("files", []) if f["file_id"].endswith((".pdf", ".epub"))), "")
        if not source:
            return []
        # Page mapping depends on the page list too, so key on the document hash as well.
        return db.cached(f"toc:{source}:{doc.get('doc_hash', '')}", lambda: table_of_contents(doc, blob_store))

    def _highlights(doc: dict[str, Any]) -> list[dict[str, Any]]:
        return db.cached(f"highlights:{doc.get('doc_hash', '')}", lambda: document_highlights(doc, blob_store))

    def _doc_or_404(doc_id: str) -> dict[str, Any]:
        doc = db.get_document(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        return doc

    @r.get("/documents/{doc_id}/toc")
    async def get_toc(doc_id: str) -> dict[str, Any]:
        """The book's table of contents, with reader page numbers."""
        doc = _doc_or_404(doc_id)
        return {"toc": await asyncio.to_thread(_toc, doc)}

    @r.get("/documents/{doc_id}/highlights")
    async def get_document_highlights(doc_id: str, format: str = "json") -> Any:
        """Text highlighted on the tablet in this book. `format=md` downloads it as Markdown."""
        doc = _doc_or_404(doc_id)
        highlights = await asyncio.to_thread(_highlights, doc)
        if format == "md":
            md = highlights_markdown([(doc.get("visible_name", "Untitled"), highlights)])
            return _markdown_download(md, doc.get("visible_name", "highlights"))
        return {"highlights": highlights}

    @r.get("/highlights")
    async def get_all_highlights(format: str = "json") -> Any:
        """Highlights from every book, newest-read book first. `format=md` downloads Markdown."""

        def collect() -> list[dict[str, Any]]:
            books = []
            for d in db.list_documents(include_deleted=False):
                if d.get("type") != "DocumentType" or d.get("file_type") not in ("pdf", "epub"):
                    continue
                doc = db.get_document(d["id"])
                found = _highlights(doc) if doc else []
                if found:
                    books.append({"doc_id": d["id"], "title": d.get("visible_name", ""),
                                  "last_opened": d.get("last_opened", ""), "highlights": found})
            books.sort(key=lambda b: int(b["last_opened"] or 0), reverse=True)
            return books

        books = await asyncio.to_thread(collect)
        if format == "md":
            return _markdown_download(highlights_markdown([(b["title"], b["highlights"]) for b in books]), "Highlights")
        return {"books": books}

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
        mode_tag = "dark" if dark else "light"
        etag = f'"{doc_hash}_{mode_tag}_v5"'

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
            png_bytes = exporter.render_thumbnail(doc_id, dark_mode=dark)
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
            svg = exporter.render_page_svg(doc_id, page_idx=page_idx, dark_mode=dark).encode("utf-8")
            # Pages change when the tablet syncs new ink, so revalidate every time (a 304 is cheap).
            headers = {"Cache-Control": "no-cache", "ETag": f'"{hashlib.sha1(svg).hexdigest()}"'}
            if request and request.headers.get("if-none-match") == headers["ETag"]:
                return Response(status_code=304, headers=headers)
            content = b"" if (request and request.method == "HEAD") else svg
            return Response(
                content=content,
                media_type="image/svg+xml",
                headers={**headers, "Content-Length": str(len(svg))},
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
                    "Cache-Control": "no-cache",
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
            clean_title = _safe_name(doc["visible_name"] if doc else "", "document")
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{clean_title}.pdf"'},
            )
        except Exception as e:
            logger.exception("Error exporting PDF for %s: %s", doc_id, e)
            raise HTTPException(status_code=500, detail=str(e))

    @r.get("/documents/{doc_id}/export/zip")
    def export_folder_zip(doc_id: str) -> FileResponse:
        """Download a folder or notebook hierarchy as a ZIP archive."""
        root_doc = db.get_document(doc_id)
        if not root_doc:
            raise HTTPException(status_code=404, detail="Document or folder not found")

        # Build on disk, not in RAM: a folder of comics can be several GB.
        fd, tmp_name = tempfile.mkstemp(suffix=".zip", dir=blob_store.settings.cache_dir)
        os.close(fd)
        tmp_path = Path(tmp_name)
        try:
            with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
                def _add_to_zip(d: dict[str, Any], prefix: str) -> None:
                    clean_name = _safe_name(d.get("visible_name", ""), "item")
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
                                zf.write(p, arcname=f"{prefix}{clean_name}.pdf", compress_type=zipfile.ZIP_STORED)
                                return
                        elif epub_file and blob_store.has(epub_file["blob_hash"]):
                            p = blob_store.get_path(epub_file["blob_hash"])
                            if p and p.is_file():
                                zf.write(p, arcname=f"{prefix}{clean_name}.epub", compress_type=zipfile.ZIP_STORED)
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
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

        return FileResponse(
            tmp_path,
            media_type="application/zip",
            filename=f"{_safe_name(root_doc.get('visible_name', ''), 'archive')}.zip",
            background=BackgroundTask(tmp_path.unlink, missing_ok=True),
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

    @r.post("/tasks/complete-all")
    async def complete_all_tasks() -> dict[str, Any]:
        """Mark every open task completed and refresh the Tasks notebook once."""
        count = db.complete_open_tasks()
        if count:
            sync_engine.refresh_tasks_notebook(editor)
        return {"ok": True, "completed": count}

    @r.post("/tasks/{task_id}/status")
    async def update_task_status(task_id: str, payload: TaskStatusRequest) -> dict[str, Any]:
        """Update task completion status and refresh the Tasks notebook."""
        ok = db.set_task_status(task_id, payload.status)
        if not ok:
            raise HTTPException(status_code=404, detail="Task not found")
        sync_engine.refresh_tasks_notebook(editor)
        return {"ok": True, "task_id": task_id, "status": payload.status}

    @r.delete("/tasks/{task_id}")
    async def delete_task(task_id: str) -> dict[str, Any]:
        """Delete an extracted task and refresh the Tasks notebook."""
        ok = db.delete_task(task_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Task not found")
        sync_engine.refresh_tasks_notebook(editor)
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
        """Get vision provider settings with container environment fallback (API key masked)."""
        from rmcompanion.intelligence.provider import get_effective_vision_config
        conf = get_effective_vision_config(db, settings=settings)
        key = conf.get("api_key", "")
        masked = f"{key[:4]}...{key[-4:]}" if len(key) > 8 else ("****" if key else "")
        return {
            "provider": conf.get("provider", "gemini"),
            "model": conf.get("model", "gemini-flash-lite-latest"),
            "api_key_set": bool(key),
            "api_key_masked": masked,
            "api_key_source": conf.get("api_key_source", "none"),
            "base_url": conf.get("base_url", ""),
        }

    @r.post("/settings/vision")
    def save_vision_settings(payload: VisionSettingsRequest) -> dict[str, Any]:
        """Save vision provider settings."""
        from rmcompanion.intelligence.provider import (
            get_effective_vision_config,
            get_vision_provider,
        )
        effective = get_effective_vision_config(db, settings=settings)

        curr_raw = db.get_state("vision_settings", "")
        existing_key = ""
        if curr_raw:
            with contextlib.suppress(ValueError):  # corrupt saved settings: fall back to env key
                existing_key = json.loads(curr_raw).get("api_key", "")

        final_key = payload.api_key.strip() if payload.api_key.strip() else (existing_key or effective.get("api_key", ""))
        conf = {
            "provider": payload.provider.lower().strip(),
            "api_key": final_key,
            "model": payload.model.strip() or "gemini-flash-lite-latest",
            "base_url": payload.base_url.strip(),
        }
        db.set_state("vision_settings", json.dumps(conf))

        if task_extractor:
            task_extractor.vision_provider = get_vision_provider(db, settings=settings)

        return {"ok": True, "provider": conf["provider"], "model": conf["model"]}

    @r.post("/settings/vision/test")
    async def test_vision_settings(payload: VisionSettingsRequest) -> dict[str, Any]:
        """Test API key and latency for vision provider with automatic environment key fallback."""
        from rmcompanion.intelligence.provider import (
            VisionProvider,
            get_effective_vision_config,
        )
        effective = get_effective_vision_config(db, settings=settings)

        provider_name = (payload.provider or effective.get("provider", "gemini")).lower().strip()
        api_key = payload.api_key.strip() or effective.get("api_key", "").strip()
        model = payload.model.strip() or effective.get("model", "gemini-flash-lite-latest").strip()
        base_url = payload.base_url.strip() or effective.get("base_url", "").strip()

        provider = VisionProvider(
            provider=provider_name,
            api_key=api_key,
            model=model,
            base_url=base_url,
        )
        try:
            return await provider.test_connection()
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @r.api_route("/settings/vision/models", methods=["GET", "POST"])
    async def list_vision_models(
        payload: VisionSettingsRequest | None = None,
        provider: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Query available vision models dynamically from provider APIs, supporting live discovery."""
        from rmcompanion.intelligence.provider import get_effective_vision_config
        effective = get_effective_vision_config(db, settings=settings)

        req_provider = (payload.provider if payload else provider) or effective.get("provider", "gemini")
        req_provider = req_provider.lower().strip()

        req_key = (payload.api_key if payload and payload.api_key.strip() else (api_key or "")).strip()
        if not req_key:
            req_key = effective.get("api_key", "").strip()

        req_base_url = (payload.base_url if payload and payload.base_url.strip() else (base_url or "")).strip()
        if not req_base_url:
            req_base_url = effective.get("base_url", "").strip()
        if not req_base_url and req_provider == "ollama":
            req_base_url = "http://localhost:11434"

        models: list[dict[str, Any]] = []
        is_live = False
        default_model = "gemini-flash-lite-latest" if req_provider == "gemini" else "gpt-4o-mini"

        cache_key = f"{req_provider}:{req_key[-8:] if req_key else ''}:{req_base_url}"
        now = time.time()
        if not force_refresh and cache_key in _LIVE_MODELS_CACHE:
            ts, cached_models = _LIVE_MODELS_CACHE[cache_key]
            if now - ts < 300:
                return {
                    "ok": True,
                    "provider": req_provider,
                    "models": cached_models,
                    "default_model": default_model,
                    "live": True,
                    "cached": True,
                }

        if req_provider == "gemini":
            if req_key:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={req_key}"
                    headers = {"x-goog-api-key": req_key}
                    async with httpx.AsyncClient(timeout=6.0) as client:
                        resp = await client.get(url, headers=headers)
                        if resp.status_code == 200:
                            data = resp.json()
                            raw_models = data.get("models", [])
                            seen: set[str] = set()
                            for m in raw_models:
                                mid = m.get("name", "").replace("models/", "").strip()
                                if not mid or "gemini" not in mid.lower():
                                    continue
                                # Strictly filter out legacy deprecated models (2.5, 2.0, 1.5, 3.0) per gemini-api-dev skill
                                if any(dep in mid.lower() for dep in ("gemini-2.5", "gemini-2.0", "gemini-1.5", "gemini-3.0")):
                                    continue
                                methods = m.get("supportedGenerationMethods", [])
                                if methods and "generateContent" not in methods:
                                    continue
                                if any(x in mid.lower() for x in ("embedding", "aqa", "imagen", "tts", "transcribe")):
                                    continue

                                display = m.get("displayName") or mid
                                desc = ""
                                if "flash-lite-latest" in mid:
                                    desc = "Recommended — Fast & Economical"
                                elif "3.5-flash-lite" in mid:
                                    desc = "Fastest & Lowest Cost Execution"
                                elif "3.1-flash-lite" in mid:
                                    desc = "High Frequency & Lightweight"
                                elif "3.8-flash" in mid:
                                    desc = "Balanced Multimodal & Accurate"
                                elif "4-argon" in mid or "argon" in mid:
                                    desc = "High Capability & Reasoning"
                                elif "flash-lite" in mid:
                                    desc = "Fast & Lightweight"
                                elif "flash" in mid:
                                    desc = "Multimodal Flash"

                                label = f"{mid} ({desc})" if desc else f"{mid} ({display})"
                                models.append({
                                    "id": mid,
                                    "name": label,
                                    "is_recommended": (mid == "gemini-flash-lite-latest"),
                                })
                                seen.add(mid)

                            # Guarantee current active models are present
                            active_current_defaults = [
                                ("gemini-flash-lite-latest", "gemini-flash-lite-latest (Recommended — Fast & Economical)", True),
                                ("gemini-3.5-flash-lite", "gemini-3.5-flash-lite (Fastest & Lowest Cost Execution)", False),
                                ("gemini-3.1-flash-lite", "gemini-3.1-flash-lite (Cost-Efficient & Lightweight)", False),
                                ("gemini-3.8-flash", "gemini-3.8-flash (Balanced Multimodal & Accurate)", False),
                                ("gemini-4-argon", "gemini-4-argon (Most Powerful Reasoning & Analysis)", False),
                            ]
                            for def_id, def_name, is_rec in active_current_defaults:
                                if def_id not in seen:
                                    models.append({
                                        "id": def_id,
                                        "name": def_name,
                                        "is_recommended": is_rec,
                                    })
                                    seen.add(def_id)

                            # Sort models: current models prioritized
                            def _gemini_sort(x: dict[str, Any]) -> tuple[int, str]:
                                i = x["id"]
                                if i == "gemini-flash-lite-latest":
                                    return (0, i)
                                if i == "gemini-3.5-flash-lite":
                                    return (1, i)
                                if i == "gemini-3.1-flash-lite":
                                    return (2, i)
                                if i == "gemini-3.8-flash":
                                    return (3, i)
                                if "4-argon" in i or "argon" in i:
                                    return (4, i)
                                if "3.5" in i:
                                    return (5, i)
                                if "3.8" in i:
                                    return (6, i)
                                return (10, i)

                            models.sort(key=_gemini_sort)
                            is_live = True
                except Exception as e:
                    logger.debug("Failed to query Gemini API for live models: %s", e)

            if not models:
                models = [
                    {"id": "gemini-flash-lite-latest", "name": "gemini-flash-lite-latest (Recommended — Fast & Economical)", "is_recommended": True},
                    {"id": "gemini-3.5-flash-lite", "name": "gemini-3.5-flash-lite (Fastest & Lowest Cost Execution)", "is_recommended": False},
                    {"id": "gemini-3.1-flash-lite", "name": "gemini-3.1-flash-lite (Cost-Efficient & Lightweight)", "is_recommended": False},
                    {"id": "gemini-3.8-flash", "name": "gemini-3.8-flash (Balanced Multimodal & Accurate)", "is_recommended": False},
                    {"id": "gemini-4-argon", "name": "gemini-4-argon (Most Powerful Reasoning & Analysis)", "is_recommended": False},
                ]
            default_model = "gemini-flash-lite-latest"

        elif req_provider in ("openai", "ollama"):
            base = req_base_url or ("http://localhost:11434" if req_provider == "ollama" else "https://api.openai.com")
            headers = {"Authorization": f"Bearer {req_key}"} if req_key else {}

            # Try /v1/models endpoint
            try:
                url = f"{base.rstrip('/')}/v1/models"
                async with httpx.AsyncClient(timeout=4.0) as client:
                    resp = await client.get(url, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        for m in data.get("data", []):
                            mid = m.get("id", "").strip()
                            if not mid:
                                continue
                            low = mid.lower()
                            if any(x in low for x in ("embedding", "whisper", "tts", "dall-e", "davinci", "babbage", "moderation")):
                                continue
                            desc = ""
                            if mid == "gpt-4o-mini":
                                desc = "Recommended — Fast Vision"
                            elif mid == "gpt-4o":
                                desc = "Omni Multimodal"
                            elif "vision" in low or "vl" in low:
                                desc = "Vision Capable"
                            label = f"{mid} ({desc})" if desc else mid
                            models.append({
                                "id": mid,
                                "name": label,
                                "is_recommended": (mid == "gpt-4o-mini"),
                            })
                        if models:
                            is_live = True
            except Exception as e:
                logger.debug("Failed /v1/models query: %s", e)

            # If Ollama and no models found via /v1/models, try Ollama /api/tags
            if not models and (req_provider == "ollama" or "11434" in base):
                try:
                    url = f"{base.rstrip('/')}/api/tags"
                    async with httpx.AsyncClient(timeout=4.0) as client:
                        resp = await client.get(url)
                        if resp.status_code == 200:
                            data = resp.json()
                            for m in data.get("models", []):
                                mname = m.get("name", "").strip()
                                if mname:
                                    is_vis = any(x in mname.lower() for x in ("vision", "vl", "llava"))
                                    desc = "Vision Capable" if is_vis else "Local Model"
                                    models.append({
                                        "id": mname,
                                        "name": f"{mname} ({desc})",
                                        "is_recommended": is_vis,
                                    })
                            if models:
                                is_live = True
                except Exception as e:
                    logger.debug("Failed /api/tags query: %s", e)

            if not models:
                if req_provider == "ollama":
                    models = [
                        {"id": "llama3.2-vision", "name": "llama3.2-vision (Local Vision)", "is_recommended": True},
                        {"id": "llava", "name": "llava (Local Vision)", "is_recommended": False},
                        {"id": "qwen2.5-vl", "name": "qwen2.5-vl (Local Vision)", "is_recommended": False},
                    ]
                    default_model = "llama3.2-vision"
                else:
                    models = [
                        {"id": "gpt-4o-mini", "name": "gpt-4o-mini (Recommended — Fast Vision)", "is_recommended": True},
                        {"id": "gpt-4o", "name": "gpt-4o (Omni Multimodal)", "is_recommended": False},
                        {"id": "chatgpt-4o-latest", "name": "chatgpt-4o-latest (Latest Omni)", "is_recommended": False},
                        {"id": "llama3.2-vision", "name": "llama3.2-vision (Local Ollama Vision)", "is_recommended": False},
                        {"id": "llava", "name": "llava (Local Ollama Vision)", "is_recommended": False},
                        {"id": "qwen2.5-vl", "name": "qwen2.5-vl (Local Ollama Vision)", "is_recommended": False},
                    ]
                    default_model = "gpt-4o-mini"

        if is_live and models:
            _LIVE_MODELS_CACHE[cache_key] = (now, models)

        return {
            "ok": True,
            "provider": req_provider,
            "models": models,
            "default_model": default_model,
            "live": is_live,
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
    async def create_notebook_endpoint(payload: CreateNotebookRequest) -> dict[str, Any]:
        """Create a new native reMarkable notebook."""
        title = payload.title.strip() or "Untitled Notebook"
        try:
            res = editor.create_notebook(
                title=title,
                initial_text=payload.initial_text,
                parent_id=payload.parent_id,
            )
            sync_engine.spawn(sync_engine.push_local_notebook(res["id"]))
            return res
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
                sync_engine.spawn(sync_engine.push_local_notebook(doc_id))
            return {"ok": True, "result": res}
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Document not found")
        except IndexError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error("Failed to update page text: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    @r.post("/documents/import-markdown")
    async def import_markdown_endpoint(payload: ImportMarkdownRequest) -> dict[str, Any]:
        """Import markdown content to a new notebook."""
        title = payload.title.strip() or "Imported Note"
        try:
            res = editor.import_markdown(
                title=title,
                markdown_content=payload.markdown,
                parent_id=payload.parent_id,
            )
            sync_engine.spawn(sync_engine.push_local_notebook(res["id"]))
            return res
        except Exception as e:
            logger.error("Failed to import markdown: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    @r.post("/tasks/export-to-notebook")
    async def export_tasks_to_notebook_endpoint(payload: ExportTasksNotebookRequest) -> dict[str, Any]:
        """Consolidate open tasks into the synced Tasks notebook and push to cloud."""
        try:
            res = sync_engine.refresh_tasks_notebook(editor, payload.notebook_title)
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
            sync_engine.spawn(sync_engine.push_local_notebook(res["id"]))
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
                sync_engine.spawn(sync_engine.push_local_notebook(res["id"]))
            else:
                target_title = payload.notebook_title or "Quick Notes"
                res = editor.append_note_to_notebook(text, target_title)
                sync_engine.spawn(sync_engine.push_local_notebook(res["id"]))
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
                    sync_engine.spawn(sync_engine.push_document(opt_pdf, filename=stem, parent_id=parent_id, file_type="pdf"))
                elif ext == "pdf":
                    res = await asyncio.to_thread(editor.import_pdf_file, title=stem, pdf_bytes=content, parent_id=parent_id)
                    imported.append({"file": orig_name, "id": res["id"], "type": "pdf", "optimized": False})
                    sync_engine.spawn(sync_engine.push_document(content, filename=stem, parent_id=parent_id, file_type="pdf"))
                elif ext == "epub":
                    res = await asyncio.to_thread(editor.import_epub_file, title=stem, epub_bytes=content, parent_id=parent_id)
                    imported.append({"file": orig_name, "id": res["id"], "type": "epub", "optimized": False})
                    sync_engine.spawn(sync_engine.push_document(content, filename=stem, parent_id=parent_id, file_type="epub"))
                elif ext in {"md", "markdown", "txt"}:
                    text_str = content.decode("utf-8", errors="replace")
                    res = await asyncio.to_thread(editor.import_markdown, title=stem, markdown_content=text_str, parent_id=parent_id)
                    imported.append({"file": orig_name, "id": res["id"], "type": "notebook", "optimized": False})
                    sync_engine.spawn(sync_engine.push_local_notebook(res["id"]))
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

    # --- Daily News & Puzzles Delivery ---

    @r.get("/delivery/settings")
    def get_delivery_settings() -> dict[str, Any]:
        """Get automated delivery preferences for news and puzzles."""
        return dm.get_settings().model_dump()

    @r.post("/delivery/settings")
    def update_delivery_settings(payload: DeliverySettings) -> dict[str, Any]:
        """Update automated delivery preferences for news and puzzles."""
        dm.update_settings(payload)
        return {"status": "ok", "settings": payload.model_dump()}

    @r.post("/delivery/newspaper/trigger")
    async def trigger_newspaper_delivery(force: bool = True) -> dict[str, Any]:
        """Trigger on-demand generation and delivery of today's morning newspaper."""
        try:
            res = await dm.deliver_newspaper(force=force)
            return res
        except Exception as e:
            logger.error("Failed delivering newspaper: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    @r.post("/delivery/puzzles/trigger")
    async def trigger_puzzles_delivery(force: bool = True) -> dict[str, Any]:
        """Trigger on-demand fetch and delivery of today's crosswords and sudoku."""
        try:
            res = await dm.deliver_puzzles(force=force)
            return res
        except Exception as e:
            logger.error("Failed delivering puzzles: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    @r.get("/delivery/rss/catalog")
    def get_rss_catalog(
        query: str = Query("", description="Keyword search query"),
        category: str = Query("All", description="Category filter"),
    ) -> dict[str, Any]:
        """Get curated list of popular RSS feeds and preset packages."""
        feeds = search_popular_feeds(query=query, category=category)
        return {
            "ok": True,
            "categories": CATEGORIES,
            "presets": PRESETS,
            "feeds": feeds,
            "total_curated": len(POPULAR_FEEDS),
        }

    @r.get("/delivery/rss/discover")
    async def discover_rss_feeds(
        url: str = Query(..., description="Website URL or domain to auto-discover RSS/Atom feeds from"),
    ) -> dict[str, Any]:
        """Auto-discover RSS/Atom feeds from a given website URL or domain."""
        discovered = await discover_feed_url(url)
        return {
            "ok": True,
            "query": url,
            "count": len(discovered),
            "discovered": discovered,
        }

    @r.post("/delivery/rss/validate")
    async def validate_rss_feed(payload: FeedValidateRequest) -> dict[str, Any]:
        """Validate an RSS feed URL and preview its recent articles."""
        result = await validate_feed(payload.url)
        return {"ok": True, "result": result}

    return r
