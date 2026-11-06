"""PyMuPDF rendering for PDF page backgrounds with smart dark mode inversion."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pymupdf

logger = logging.getLogger(__name__)


def render_pdf_page_image(
    pdf_source: bytes | Path,
    page_num: int,
    dark_mode: bool = False,
    dpi: int = 150,
    max_dim: int = 1920,
    format: str = "jpeg",
) -> tuple[bytes, int, int]:
    """Render a single PDF page to JPEG/PNG with optional smart dark inversion.

    Returns:
        (image_bytes, width, height)
    """
    # Opening by path lets MuPDF read only the pages it needs (1 GB comic: 0.2s vs 4.7s per page)
    if isinstance(pdf_source, Path):
        doc = pymupdf.open(pdf_source, filetype="pdf")
    else:
        doc = pymupdf.open(stream=pdf_source, filetype="pdf")
    try:
        total_pages = len(doc)
        if total_pages == 0:
            raise ValueError("PDF document contains no pages")

        idx = max(0, min(page_num, total_pages - 1))
        page = doc[idx]

        max_page_dim = max(float(page.rect.width), float(page.rect.height), 1.0)
        target_zoom = dpi / 72.0
        if max_page_dim * target_zoom > max_dim:
            zoom = max_dim / max_page_dim
        else:
            zoom = target_zoom

        matrix = pymupdf.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix, alpha=False)

        width, height = pix.width, pix.height
        img_fmt = "jpeg" if format.lower() == "jpeg" else "png"
        img_kwargs = {"jpg_quality": 85} if img_fmt == "jpeg" else {}

        if not dark_mode:
            return pix.tobytes(img_fmt, **img_kwargs), width, height

        # 1. Structural Comic / Graphic Novel Detection
        images = page.get_images()
        text_len = len(page.get_text("text").strip())
        page_area = float(page.rect.width * page.rect.height) if page.rect else 1.0
        img_area = sum(float(r.width * r.height) for im in images for r in page.get_image_rects(im[0]))
        image_coverage = (img_area / page_area) if page_area > 0 else 0.0

        is_comic = image_coverage > 0.55 or (len(images) > 0 and text_len < 100 and image_coverage > 0.25)
        if is_comic:
            # Preserve authentic artwork without blanket inversion
            return pix.tobytes(img_fmt, **img_kwargs), width, height

        # 2. Text Document Inversion
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape((height, width, 3)).copy()

        # Invert paper and text: map white paper (~255) to dark zinc (~24), black ink (~0) to light zinc (~244)
        inverted = 255 - img
        mapped = (inverted.astype(np.float32) * (220.0 / 255.0) + 24.0).clip(0, 255).astype(np.uint8)

        # 3. Protect embedded figures/photos on text pages
        if images:
            for img_info in images:
                for r in page.get_image_rects(img_info[0]):
                    rx0 = max(0, min(int(r.x0 * zoom), width))
                    ry0 = max(0, min(int(r.y0 * zoom), height))
                    rx1 = max(0, min(int(r.x1 * zoom), width))
                    ry1 = max(0, min(int(r.y1 * zoom), height))
                    if rx1 > rx0 and ry1 > ry0:
                        mapped[ry0:ry1, rx0:rx1] = img[ry0:ry1, rx0:rx1]

        out_pix = pymupdf.Pixmap(pymupdf.csRGB, width, height, mapped.tobytes(), False)
        return out_pix.tobytes(img_fmt, **img_kwargs), width, height
    finally:
        doc.close()
