"""PyMuPDF rendering for PDF page backgrounds with smart dark mode inversion."""

from __future__ import annotations

import logging

import numpy as np
import pymupdf

logger = logging.getLogger(__name__)


def render_pdf_page_image(
    pdf_bytes: bytes,
    page_num: int,
    dark_mode: bool = False,
    dpi: int = 150,
) -> tuple[bytes, int, int]:
    """Render a single PDF page to PNG with optional smart dark inversion.

    Returns:
        (png_bytes, width, height)
    """
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        total_pages = len(doc)
        if total_pages == 0:
            raise ValueError("PDF document contains no pages")

        idx = max(0, min(page_num, total_pages - 1))
        page = doc[idx]

        zoom = dpi / 72.0
        matrix = pymupdf.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix, alpha=False)

        width, height = pix.width, pix.height

        if not dark_mode:
            return pix.tobytes("png"), width, height

        # Smart dark mode inversion for PDF pages
        # Convert pixmap buffer to numpy array (H, W, 3)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape((height, width, 3)).copy()

        # Check if the page is primarily an image/comic with high color saturation
        # Calculate saturation: max(RGB) - min(RGB)
        rgb_max = img.max(axis=-1)
        rgb_min = img.min(axis=-1)
        saturation = rgb_max - rgb_min
        color_pixel_ratio = np.count_nonzero(saturation > 40) / (width * height)

        if color_pixel_ratio > 0.35:
            # Color-rich page (e.g. comic, photo, colored chart):
            # Only slightly dim the background rather than inverting photos
            dimmed = (img.astype(np.float32) * 0.9).astype(np.uint8)
            out_pix = pymupdf.Pixmap(pymupdf.csRGB, width, height, dimmed.tobytes(), False)
            return out_pix.tobytes("png"), width, height

        # Standard document/text page: invert lightness while keeping hues
        # Linear inversion: 255 - value, then map white paper to zinc-900 (24, 24, 27)
        inverted = 255 - img
        # Scale range so bright white (now 0) becomes ~24 and black text (now 255) becomes ~244
        mapped = (inverted.astype(np.float32) * (220.0 / 255.0) + 24.0).clip(0, 255).astype(np.uint8)

        out_pix = pymupdf.Pixmap(pymupdf.csRGB, width, height, mapped.tobytes(), False)
        return out_pix.tobytes("png"), width, height
    finally:
        doc.close()
