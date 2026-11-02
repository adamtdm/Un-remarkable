"""High-level document exporter and page renderer with disk caching."""

from __future__ import annotations

import base64
import hashlib
import logging
from pathlib import Path

import numpy as np
import pymupdf

from rmcompanion.config import Settings, get_settings
from rmcompanion.render.notebook import RM_PRO_HEIGHT, RM_PRO_WIDTH, render_rm_to_svg
from rmcompanion.render.pdf_render import render_pdf_page_image
from rmcompanion.store.blob_store import BlobStore
from rmcompanion.store.db import Database

logger = logging.getLogger(__name__)


class Exporter:
    """Manages document rendering to SVG, PNG, and annotated PDF."""

    def __init__(
        self,
        db: Database | None = None,
        blob_store: BlobStore | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.db = db or Database(settings=self.settings)
        self.blob_store = blob_store or BlobStore(settings=self.settings)

    def _get_cache_path(self, key: str, ext: str) -> Path:
        prefix = "thumb_" if key.startswith("thumb_") else ("page_" if key.startswith("page_") else "")
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
        filename = f"{prefix}{digest}.{ext}"
        return self.settings.cache_dir / filename

    def render_page_svg(
        self,
        doc_id: str,
        page_idx: int = 0,
        dark_mode: bool = False,
    ) -> str:
        """Render a single document page to SVG."""
        doc = self.db.get_document(doc_id)
        if not doc:
            raise FileNotFoundError(f"Document {doc_id} not found")

        doc_hash = doc.get("doc_hash", "")
        pages = doc.get("pages", [])
        if not pages:
            # Empty or uninitialized document
            return self._blank_svg(dark_mode)

        if page_idx < 0 or page_idx >= len(pages):
            page_idx = 0

        target_page = pages[page_idx]
        page_id = target_page.get("page_id", "")
        redir = target_page.get("redir", -1)

        files = {f["file_id"]: f["blob_hash"] for f in doc.get("files", [])}
        file_type = doc.get("file_type", "notebook")
        pdf_file_key = next((k for k in files if k.endswith(".pdf")), None)
        pdf_blob_hash = files.get(pdf_file_key, "") if pdf_file_key else ""
        rm_file_key = f"{doc_id}/{page_id}.rm"
        rm_blob_hash = files.get(rm_file_key, "")

        # Cache key based on actual content blob hashes, not mutable metadata doc_hash
        cache_key = f"page_{doc_id}_{page_idx}_{page_id}_{redir}_{pdf_blob_hash}_{rm_blob_hash}_{'dark' if dark_mode else 'light'}_v4"
        cache_file = self._get_cache_path(cache_key, "svg")
        if cache_file.is_file():
            return cache_file.read_text(encoding="utf-8")

        # 1. Notebook rendering
        if file_type == "notebook" or not any(k.endswith(".pdf") for k in files):
            rm_file_key = f"{doc_id}/{page_id}.rm"
            rm_blob_hash = files.get(rm_file_key)

            if rm_blob_hash and self.blob_store.has(rm_blob_hash):
                rm_bytes = self.blob_store.get(rm_blob_hash)
                svg_content = render_rm_to_svg(rm_bytes, dark_mode=dark_mode, include_background=True)
            else:
                svg_content = self._blank_svg(dark_mode)

        # 2. PDF rendering with handwritten annotations overlay
        else:
            pdf_file_key = next((k for k in files if k.endswith(".pdf")), None)
            if not pdf_file_key or not self.blob_store.has(files[pdf_file_key]):
                svg_content = self._blank_svg(dark_mode)
            else:
                pdf_blob = self.blob_store.get(files[pdf_file_key])
                actual_pdf_page = redir if redir >= 0 else page_idx

                # Render PDF page to image
                img_bytes, width, height = render_pdf_page_image(
                    pdf_blob, actual_pdf_page, dark_mode=dark_mode, dpi=150
                )
                b64_img = base64.b64encode(img_bytes).decode("ascii")
                mime_type = "image/jpeg" if img_bytes.startswith(b"\xff\xd8") else "image/png"

                # Check if there are stroke annotations for this page
                rm_file_key = f"{doc_id}/{page_id}.rm"
                rm_blob_hash = files.get(rm_file_key)
                ink_svg = ""
                if rm_blob_hash and self.blob_store.has(rm_blob_hash):
                    try:
                        rm_bytes = self.blob_store.get(rm_blob_hash)
                        # Render strokes with transparent background matching PDF dimensions
                        ink_svg = render_rm_to_svg(
                            rm_bytes,
                            dark_mode=dark_mode,
                            include_background=False,
                            target_width=width,
                            target_height=height,
                        )
                        # Strip outer <svg> and </svg> tags to embed inside composite SVG
                        ink_svg = self._extract_inner_svg(ink_svg)
                    except Exception as e:
                        logger.warning("Failed to render ink overlay for %s: %s", doc_id, e)

                half_w = width // 2
                svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-half_w} 0 {width} {height}" width="{width}" height="{height}">
  <image href="data:{mime_type};base64,{b64_img}" x="{-half_w}" y="0" width="{width}" height="{height}" />
  {ink_svg}
</svg>"""

        # Save to cache
        try:
            cache_file.write_text(svg_content, encoding="utf-8")
        except OSError:
            pass

        return svg_content

    def render_page_png(
        self,
        doc_id: str,
        page_idx: int = 0,
        dark_mode: bool = False,
    ) -> bytes:
        """Render a single page to PNG bytes."""
        cache_key = f"png_{doc_id}_{page_idx}_{'dark' if dark_mode else 'light'}"
        cache_file = self._get_cache_path(cache_key, "png")
        if cache_file.is_file():
            return cache_file.read_bytes()

        svg_content = self.render_page_svg(doc_id, page_idx=page_idx, dark_mode=dark_mode)

        # PyMuPDF renders SVG string directly to pixmap
        doc = pymupdf.open(stream=svg_content.encode("utf-8"), filetype="svg")
        try:
            pix = doc[0].get_pixmap(dpi=150)
            png_bytes = pix.tobytes("png")
            try:
                cache_file.write_bytes(png_bytes)
            except OSError:
                pass
            return png_bytes
        finally:
            doc.close()

    def render_thumbnail(
        self,
        doc_id: str,
        dark_mode: bool = False,
        max_width: int = 320,
    ) -> bytes:
        """Render a fast, lightweight, disk-cached thumbnail PNG with smart dark-mode note detection."""
        doc = self.db.get_document(doc_id)
        if not doc:
            raise FileNotFoundError(f"Document {doc_id} not found")

        doc_hash = doc.get("doc_hash", "")
        mode_tag = "dark" if dark_mode else "light"
        cache_key = f"thumb_{doc_hash}_{max_width}_{mode_tag}_v4"
        cache_file = self._get_cache_path(cache_key, "png")
        if cache_file.is_file():
            return cache_file.read_bytes()

        pages = doc.get("pages", [])
        if not pages:
            blank_png = self._blank_thumbnail(dark_mode, max_width)
            try:
                cache_file.write_bytes(blank_png)
            except OSError:
                pass
            return blank_png

        target_page = pages[0]
        page_id = target_page.get("page_id", "")
        redir = target_page.get("redir", -1)
        files = {f["file_id"]: f["blob_hash"] for f in doc.get("files", [])}
        file_type = doc.get("file_type", "notebook")
        pdf_file_key = next((k for k in files if k.endswith(".pdf")), None)

        png_bytes = b""

        # Case 1: PDF / EPUB document (covers are rendered in authentic original colors, never inverted)
        if pdf_file_key and self.blob_store.has(files[pdf_file_key]):
            try:
                pdf_blob = self.blob_store.get(files[pdf_file_key])
                actual_page = redir if redir >= 0 else 0
                with pymupdf.open("pdf", pdf_blob) as pdf_doc:
                    if 0 <= actual_page < len(pdf_doc):
                        p = pdf_doc[actual_page]
                        scale = max_width / max(float(p.rect.width), 1.0)
                        pix = p.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)

                        # Composite any handwritten .rm strokes on page 0 if present
                        rm_file_key = f"{doc_id}/{page_id}.rm"
                        rm_blob_hash = files.get(rm_file_key)
                        if rm_blob_hash and self.blob_store.has(rm_blob_hash):
                            try:
                                rm_bytes = self.blob_store.get(rm_blob_hash)
                                stroke_svg = render_rm_to_svg(
                                    rm_bytes,
                                    dark_mode=False,
                                    include_background=False,
                                )
                                with pymupdf.open(
                                    stream=stroke_svg.encode("utf-8"), filetype="svg"
                                ) as sdoc:
                                    spage = sdoc[0]
                                    sx = pix.width / max(float(spage.rect.width), 1.0)
                                    sy = pix.height / max(float(spage.rect.height), 1.0)
                                    spix = spage.get_pixmap(
                                        matrix=pymupdf.Matrix(sx, sy), alpha=True
                                    )
                                    if (
                                        spix.width == pix.width
                                        and spix.height == pix.height
                                    ):
                                        base_arr = (
                                            np.frombuffer(pix.samples, dtype=np.uint8)
                                            .reshape((pix.height, pix.width, 3))
                                            .astype(np.float32)
                                        )
                                        over_arr = (
                                            np.frombuffer(spix.samples, dtype=np.uint8)
                                            .reshape((spix.height, spix.width, 4))
                                            .astype(np.float32)
                                        )
                                        alpha = over_arr[:, :, 3:4] / 255.0
                                        blended = (
                                            over_arr[:, :, :3] * alpha
                                            + base_arr * (1.0 - alpha)
                                        ).clip(0, 255).astype(np.uint8)
                                        pix = pymupdf.Pixmap(
                                            pymupdf.csRGB,
                                            pix.width,
                                            pix.height,
                                            blended.tobytes(),
                                            False,
                                        )
                            except Exception as e:
                                logger.debug(
                                    "Failed to overlay strokes on PDF thumbnail %s: %s",
                                    doc_id,
                                    e,
                                )

                        png_bytes = pix.tobytes("png")
                    else:
                        png_bytes = self._blank_thumbnail(dark_mode, max_width)
            except Exception as e:
                logger.warning("Failed to render PDF thumbnail for %s: %s", doc_id, e)
                png_bytes = self._blank_thumbnail(dark_mode, max_width)

        # Case 2: Native Notebook (.rm file) (theme-aware paper and ink)
        else:
            rm_file_key = f"{doc_id}/{page_id}.rm"
            rm_blob_hash = files.get(rm_file_key)
            if rm_blob_hash and self.blob_store.has(rm_blob_hash):
                try:
                    rm_bytes = self.blob_store.get(rm_blob_hash)
                    svg_content = render_rm_to_svg(
                        rm_bytes,
                        dark_mode=dark_mode,
                        include_background=True,
                    )
                    with pymupdf.open(
                        stream=svg_content.encode("utf-8"), filetype="svg"
                    ) as svg_doc:
                        spage = svg_doc[0]
                        scale = max_width / max(float(spage.rect.width), 1.0)
                        pix = spage.get_pixmap(matrix=pymupdf.Matrix(scale, scale))
                        png_bytes = pix.tobytes("png")
                except Exception as e:
                    logger.warning(
                        "Failed to render notebook thumbnail for %s: %s", doc_id, e
                    )
                    png_bytes = self._blank_thumbnail(dark_mode, max_width)
            else:
                png_bytes = self._blank_thumbnail(dark_mode, max_width)

        try:
            cache_file.write_bytes(png_bytes)
        except OSError:
            pass

        return png_bytes

    def warm_thumbnail(self, doc_id: str, doc_hash: str = "") -> None:
        """Pre-generate light and dark thumbnails in cache."""
        try:
            self.render_thumbnail(doc_id, dark_mode=True)
            self.render_thumbnail(doc_id, dark_mode=False)
        except Exception as e:
            logger.debug("Thumbnail warm error for %s: %s", doc_id, e)

    def clear_thumbnail_cache(self) -> int:
        """Purge all cached thumbnail and page rendering images."""
        count = 0
        try:
            for pattern in ("thumb_*.png", "page_*.svg", "*.png", "*.svg"):
                for p in self.settings.cache_dir.glob(pattern):
                    try:
                        p.unlink()
                        count += 1
                    except OSError:
                        pass
        except Exception as e:
            logger.warning("Failed to clear thumbnail cache: %s", e)
        return count

    def _blank_thumbnail(self, dark_mode: bool, max_width: int = 320) -> bytes:
        """Generate a small placeholder thumbnail PNG."""
        h = int(max_width * 4 / 3)
        doc = pymupdf.open()
        p = doc.new_page(width=max_width, height=h)
        bg = (0.1, 0.1, 0.11) if dark_mode else (0.96, 0.96, 0.96)
        p.draw_rect(pymupdf.Rect(0, 0, max_width, h), fill=bg)
        pix = p.get_pixmap()
        b = pix.tobytes("png")
        doc.close()
        return b

    def export_annotated_pdf(self, doc_id: str, dark_mode: bool = False) -> bytes:
        """Export complete document as multi-page PDF with annotations."""
        doc = self.db.get_document(doc_id)
        if not doc:
            raise FileNotFoundError(f"Document {doc_id} not found")

        pages = doc.get("pages", [])
        if not pages:
            # Empty PDF
            out_doc = pymupdf.open()
            out_doc.new_page(width=RM_PRO_WIDTH * 72 / 229, height=RM_PRO_HEIGHT * 72 / 229)
            pdf_bytes = out_doc.tobytes()
            out_doc.close()
            return pdf_bytes

        out_pdf = pymupdf.open()
        try:
            for idx in range(len(pages)):
                svg_data = self.render_page_svg(doc_id, page_idx=idx, dark_mode=dark_mode)
                svg_doc = pymupdf.open(stream=svg_data.encode("utf-8"), filetype="svg")
                try:
                    pdf_page_bytes = svg_doc.convert_to_pdf()
                    with pymupdf.open("pdf", pdf_page_bytes) as temp_pdf:
                        out_pdf.insert_pdf(temp_pdf)
                finally:
                    svg_doc.close()

            return out_pdf.tobytes()
        finally:
            out_pdf.close()

    def _blank_svg(self, dark_mode: bool) -> str:
        bg = "#18181b" if dark_mode else "#ffffff"
        half_w = RM_PRO_WIDTH // 2
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-half_w} 0 {RM_PRO_WIDTH} {RM_PRO_HEIGHT}" '
            f'width="{RM_PRO_WIDTH}" height="{RM_PRO_HEIGHT}">'
            f'<rect x="{-half_w}" y="0" width="{RM_PRO_WIDTH}" height="{RM_PRO_HEIGHT}" fill="{bg}"/>'
            f'</svg>'
        )

    def _extract_inner_svg(self, svg_str: str) -> str:
        """Strip outer <svg...> and </svg> tags."""
        start = svg_str.find(">")
        end = svg_str.rfind("</svg>")
        if start != -1 and end != -1 and end > start:
            return svg_str[start + 1 : end]
        return svg_str
