"""Comic and oversized document converter tuned for reMarkable devices (Paper Pro, RM2, RM1).

Converts heavy fixed-layout EPUBs, bulky PDFs, and CBZ comic archives into
lean, single-layer PDFs sized to the target reMarkable screen.
"""

from __future__ import annotations

import asyncio
import io
import logging
import time
import uuid
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pymupdf

from rmcompanion.config import Settings, get_settings
from rmcompanion.store.blob_store import BlobStore
from rmcompanion.store.db import Database

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QualityProfile:
    stop: int
    name: str
    max_height: int
    max_width: int
    jpeg_quality: int
    description: str


# 5-Stop Quality Slider Profiles
# Paper Pro physical screen is 1620 x 2160 portrait (2160 x 1620 landscape) at 229 PPI
DEVICE_SPECS: dict[str, dict[str, Any]] = {
    "paper_pro": {"name": "reMarkable Paper Pro (2160×1620, Color Canvas)", "max_w": 1620, "max_h": 2160, "grayscale": False},
    "paper_pro_move": {"name": "reMarkable Paper Pro - Move / Landscape (1620×2160)", "max_w": 2160, "max_h": 1620, "grayscale": False},
    "rm2": {"name": "reMarkable 2 (1872×1404, Monochrome Canvas)", "max_w": 1404, "max_h": 1872, "grayscale": True},
    "rm1": {"name": "reMarkable 1 (1872×1404, Monochrome Canvas)", "max_w": 1404, "max_h": 1872, "grayscale": True},
}

QUALITY_PROFILES: dict[int, QualityProfile] = {
    1: QualityProfile(
        stop=1,
        name="Smallest",
        max_height=1600,
        max_width=1200,
        jpeg_quality=65,
        description="Fastest page turns, ultra-low memory (~75% reduction)",
    ),
    2: QualityProfile(
        stop=2,
        name="Compact",
        max_height=1920,
        max_width=1440,
        jpeg_quality=72,
        description="Snappy paging with great legibility (~65% reduction)",
    ),
    3: QualityProfile(
        stop=3,
        name="Balanced",
        max_height=2160,
        max_width=1620,
        jpeg_quality=82,
        description="1:1 native reMarkable pixel match (device screen target) - Recommended",
    ),
    4: QualityProfile(
        stop=4,
        name="Sharp",
        max_height=2560,
        max_width=1920,
        jpeg_quality=88,
        description="Crisp fine text and detailed line art (~40% reduction)",
    ),
    5: QualityProfile(
        stop=5,
        name="Best",
        max_height=3000,
        max_width=2250,
        jpeg_quality=92,
        description="Maximum preservation of master scans (~10% reduction)",
    ),
}


class ConverterEngine:
    """Manages document optimization jobs for fast e-ink rendering."""

    MAX_CONVERSION_JOBS: int = 20

    def __init__(
        self,
        db: Database | None = None,
        blob_store: BlobStore | None = None,
        settings: Settings | None = None,
        sync_engine: Any = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.db = db or Database(settings=self.settings)
        self.blob_store = blob_store or BlobStore(settings=self.settings)
        self.sync_engine = sync_engine

        self.output_dir = self.settings.cache_dir / "converted"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._jobs: dict[str, dict[str, Any]] = {}
        self._cleanup_stale_outputs()

    def _cleanup_stale_outputs(self, max_age_hours: int = 24) -> None:
        """Purge temporary conversion PDFs older than max_age_hours."""
        try:
            now = time.time()
            cutoff = now - (max_age_hours * 3600)
            for f in self.output_dir.glob("*.pdf"):
                if f.is_file() and f.stat().st_mtime < cutoff:
                    f.unlink(missing_ok=True)
        except Exception as e:
            logger.debug("Failed to clean up stale converter outputs: %s", e)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[dict[str, Any]]:
        return list(reversed(list(self._jobs.values())))

    def convert_sync(
        self,
        input_source: bytes | Path | None = None,
        input_type: str = "pdf",
        quality_stop: int = 3,
        split_spreads: bool = False,
        manga_mode: bool = False,
        progress_cb: Callable[[int, int, str], None] | None = None,
        out_path: Path | None = None,
        device: str = "paper_pro",
        *,
        input_bytes: bytes | None = None,
    ) -> bytes:
        """Synchronously convert document bytes or file path into an optimized PDF."""
        source = input_source if input_source is not None else input_bytes
        if source is None:
            raise ValueError("No input source provided")

        profile = QUALITY_PROFILES.get(quality_stop, QUALITY_PROFILES[3])
        out_pdf = pymupdf.open()

        # Handle CBZ (ZIP of images)
        if input_type.lower() == "cbz":
            zip_target = source if isinstance(source, Path) else io.BytesIO(source)
            with zipfile.ZipFile(zip_target) as z:
                valid_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
                img_names = sorted(
                    [n for n in z.namelist() if Path(n).suffix.lower() in valid_exts]
                )
                total = len(img_names)
                for idx, name in enumerate(img_names):
                    if progress_cb:
                        progress_cb(idx + 1, total, f"Processing page {idx + 1} of {total}")
                    raw_img = z.read(name)
                    with pymupdf.open(stream=raw_img, filetype="image") as img_doc:
                        self._process_and_insert_page(
                            img_doc[0], out_pdf, profile, split_spreads, manga_mode, device=device
                        )
                    time.sleep(0.004)

        # Handle PDF or EPUB
        else:
            filetype = "epub" if input_type.lower() == "epub" else "pdf"
            if isinstance(source, Path):
                in_doc_ctx = pymupdf.open(str(source), filetype=filetype)
            else:
                in_doc_ctx = pymupdf.open(stream=source, filetype=filetype)

            with in_doc_ctx as in_doc:
                total = len(in_doc)
                for idx, page in enumerate(in_doc):
                    if progress_cb:
                        progress_cb(idx + 1, total, f"Processing page {idx + 1} of {total}")
                    self._process_and_insert_page(
                        page, out_pdf, profile, split_spreads, manga_mode, device=device
                    )
                    time.sleep(0.004)

        if out_path:
            out_pdf.save(str(out_path), deflate=True, garbage=4, clean=True)
            out_pdf.close()
            return b""
        else:
            result_bytes = out_pdf.tobytes(deflate=True, garbage=4, clean=True)
            out_pdf.close()
            return result_bytes

    def _process_and_insert_page(
        self,
        page: pymupdf.Page,
        out_doc: pymupdf.Document,
        profile: QualityProfile,
        split_spreads: bool,
        manga_mode: bool,
        device: str = "paper_pro",
    ) -> None:
        """Render page or sub-pages to target resolution and insert as compressed JPEG."""
        rect = page.rect
        is_spread = rect.width > rect.height * 1.25

        if is_spread and split_spreads:
            # Split double spread into two portrait pages
            half_w = rect.width / 2.0
            r_left = pymupdf.Rect(rect.x0, rect.y0, rect.x0 + half_w, rect.y1)
            r_right = pymupdf.Rect(rect.x0 + half_w, rect.y0, rect.x1, rect.y1)

            sub_rects = [r_right, r_left] if manga_mode else [r_left, r_right]
            for sub_r in sub_rects:
                self._render_rect_to_page(page, sub_r, out_doc, profile, is_landscape=False, device=device)
        else:
            self._render_rect_to_page(page, rect, out_doc, profile, is_landscape=is_spread, device=device)

    def _render_rect_to_page(
        self,
        page: pymupdf.Page,
        clip_rect: pymupdf.Rect,
        out_doc: pymupdf.Document,
        profile: QualityProfile,
        is_landscape: bool,
        device: str = "paper_pro",
    ) -> None:
        dev_info = DEVICE_SPECS.get(device, DEVICE_SPECS["paper_pro"])
        dev_w = dev_info["max_w"]
        dev_h = dev_info["max_h"]

        base_w = min(profile.max_width, dev_w)
        base_h = min(profile.max_height, dev_h)

        target_w = base_h if is_landscape else base_w
        target_h = base_w if is_landscape else base_h

        scale_x = target_w / clip_rect.width
        scale_y = target_h / clip_rect.height
        scale = min(scale_x, scale_y)

        mat = pymupdf.Matrix(scale, scale)
        colorspace = pymupdf.csGRAY if dev_info.get("grayscale") else pymupdf.csRGB
        pix = page.get_pixmap(matrix=mat, clip=clip_rect, colorspace=colorspace, alpha=False)
        jpg_bytes = pix.tobytes(output="jpeg", jpg_quality=profile.jpeg_quality)

        new_page = out_doc.new_page(width=pix.width, height=pix.height)
        new_page.insert_image(new_page.rect, stream=jpg_bytes)

    async def start_job_from_doc(
        self,
        doc_id: str,
        quality_stop: int = 3,
        split_spreads: bool = False,
        manga_mode: bool = False,
        device: str = "paper_pro",
    ) -> str:
        """Start asynchronous conversion of an existing library document."""
        doc = self.db.get_document(doc_id)
        if not doc:
            raise ValueError(f"Document {doc_id} not found")

        files = {f["file_id"]: f["blob_hash"] for f in doc.get("files", [])}

        # Look for PDF or EPUB blob
        pdf_file = next((k for k in files if k.endswith(".pdf")), None)
        epub_file = next((k for k in files if k.endswith(".epub")), None)

        if pdf_file and self.blob_store.has(files[pdf_file]):
            blob_hash = files[pdf_file]
            input_type = "pdf"
        elif epub_file and self.blob_store.has(files[epub_file]):
            blob_hash = files[epub_file]
            input_type = "epub"
        else:
            raise ValueError(f"No PDF or EPUB blob found for document {doc_id}")

        blob_path = self.blob_store.get_path(blob_hash)
        if not blob_path:
            raise ValueError(f"Blob file missing from disk: {blob_hash}")
        original_size = blob_path.stat().st_size
        title = doc.get("visible_name", "document")
        parent_id = doc.get("parent_id", "")
        return self._launch_job(
            source_name=f"{title}.{input_type}",
            input_source=blob_path,
            input_type=input_type,
            original_size=original_size,
            quality_stop=quality_stop,
            split_spreads=split_spreads,
            manga_mode=manga_mode,
            device=device,
            parent_id=parent_id,
        )

    async def start_job_from_upload(
        self,
        filename: str,
        input_bytes: bytes,
        quality_stop: int = 3,
        split_spreads: bool = False,
        manga_mode: bool = False,
        device: str = "paper_pro",
        parent_id: str = "",
    ) -> str:
        """Start asynchronous conversion of an uploaded file."""
        ext = Path(filename).suffix.lstrip(".").lower()
        if ext not in {"pdf", "epub", "cbz"}:
            raise ValueError(f"Unsupported format: .{ext} (must be .pdf, .epub, or .cbz)")

        return self._launch_job(
            source_name=filename,
            input_source=input_bytes,
            input_type=ext,
            original_size=len(input_bytes),
            quality_stop=quality_stop,
            split_spreads=split_spreads,
            manga_mode=manga_mode,
            device=device,
            parent_id=parent_id,
        )

    def _launch_job(
        self,
        source_name: str,
        input_source: bytes | Path,
        input_type: str,
        original_size: int,
        quality_stop: int,
        split_spreads: bool,
        manga_mode: bool,
        device: str = "paper_pro",
        parent_id: str = "",
    ) -> str:
        # Evict oldest jobs when exceeding capacity
        while len(self._jobs) >= self.MAX_CONVERSION_JOBS:
            oldest_id = next(iter(self._jobs))
            old_job = self._jobs.pop(oldest_id, None)
            if old_job:
                try:
                    Path(old_job.get("output_path", "")).unlink(missing_ok=True)
                except Exception as e:
                    logger.debug("Failed to delete evicted job file %s: %s", oldest_id, e)

        job_id = str(uuid.uuid4())
        out_filename = f"{Path(source_name).stem}_optimized.pdf"
        out_path = self.output_dir / f"{job_id}.pdf"

        job_info: dict[str, Any] = {
            "job_id": job_id,
            "source_name": source_name,
            "output_filename": out_filename,
            "output_path": str(out_path),
            "quality_stop": quality_stop,
            "quality_name": QUALITY_PROFILES.get(quality_stop, QUALITY_PROFILES[3]).name,
            "device": device,
            "status": "processing",
            "progress_percent": 0,
            "current_page": 0,
            "total_pages": 0,
            "original_size": original_size,
            "result_size": 0,
            "reduction_percent": 0.0,
            "started_at": time.time(),
            "completed_at": 0.0,
            "error": "",
        }
        self._jobs[job_id] = job_info

        async def _run() -> None:
            loop = asyncio.get_running_loop()

            def _progress(current: int, total: int, msg: str) -> None:
                job_info["current_page"] = current
                job_info["total_pages"] = total
                job_info["progress_percent"] = int((current / max(total, 1)) * 100)

            try:
                await loop.run_in_executor(
                    None,
                    self.convert_sync,
                    input_source,
                    input_type,
                    quality_stop,
                    split_spreads,
                    manga_mode,
                    _progress,
                    out_path,
                    device,
                )
                result_size = out_path.stat().st_size
                job_info["status"] = "done"
                job_info["result_size"] = result_size
                if job_info["original_size"] > 0:
                    red = (
                        1.0 - (result_size / job_info["original_size"])
                    ) * 100.0
                    job_info["reduction_percent"] = round(red, 1)
                job_info["completed_at"] = time.time()
                logger.info(
                    "Job %s completed: %s -> %d bytes (%.1f%% reduction)",
                    job_id,
                    source_name,
                    result_size,
                    job_info["reduction_percent"],
                )

                if self.sync_engine:
                    try:
                        clean_stem = Path(source_name).stem
                        dest_name = f"{clean_stem} (Optimized)"
                        await self.sync_engine.push_document(
                            file_bytes=out_path.read_bytes(),
                            filename=dest_name,
                            parent_id=parent_id,
                            file_type="pdf",
                        )
                        logger.info("Auto-synced optimized document %s to reMarkable Cloud", dest_name)
                    except Exception as exc:
                        logger.warning("Failed to auto-sync converted document to cloud: %s", exc)
            except Exception as e:
                logger.exception("Error processing job %s: %s", job_id, e)
                job_info["status"] = "error"
                job_info["error"] = str(e)

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_run())
        except RuntimeError:
            pass
        return job_id
