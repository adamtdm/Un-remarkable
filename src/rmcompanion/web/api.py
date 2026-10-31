"""REST API endpoints for reMarkable Companion."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel

from rmcompanion.cloud.auth import AuthManager
from rmcompanion.config import Settings
from rmcompanion.render.exporter import Exporter
from rmcompanion.store.blob_store import BlobStore
from rmcompanion.store.db import Database
from rmcompanion.sync.engine import SyncEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


class RegisterCodeRequest(BaseModel):
    code: str


def get_router(
    db: Database,
    blob_store: BlobStore,
    auth: AuthManager,
    sync_engine: SyncEngine,
    exporter: Exporter,
    settings: Settings | None = None,
) -> APIRouter:
    r = APIRouter(prefix="/api")

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
            device_token = await auth.register_device(code)
            # Trigger immediate sync
            asyncio_task = sync_engine.sync_once()
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
    ) -> list[dict[str, Any]]:
        """List documents in a given folder."""
        pid = parent_id if parent_id else ""
        return db.list_documents(parent_id=pid, include_deleted=include_deleted, file_type=file_type)

    @r.get("/documents/{doc_id}")
    def get_document(doc_id: str) -> dict[str, Any]:
        """Get document metadata, pages, and version history."""
        doc = db.get_document(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        versions = db.list_versions(doc_id)
        doc["versions"] = versions
        return doc

    @r.get("/documents/{doc_id}/pages/{page_idx}/svg")
    def get_page_svg(doc_id: str, page_idx: int = 0, dark: bool = False) -> Response:
        """Render a single page to SVG."""
        try:
            svg = exporter.render_page_svg(doc_id, page_idx=page_idx, dark_mode=dark)
            return Response(content=svg, media_type="image/svg+xml")
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
            return Response(content=png, media_type="image/png")
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

    @r.get("/search")
    def search(q: str = Query(..., min_length=1), limit: int = 25) -> list[dict[str, Any]]:
        """Full-text search across documents and notes."""
        return db.search(query=q, limit=limit)

    @r.get("/snapshots")
    def list_snapshots(limit: int = 30) -> list[dict[str, Any]]:
        """List historical sync snapshots."""
        return db.list_snapshots(limit=limit)

    return r
