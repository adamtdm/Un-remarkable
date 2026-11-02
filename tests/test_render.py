"""Tests for SVG and PNG rendering of .rm v6 scene files."""

from pathlib import Path

import pymupdf
import pytest

from rmcompanion.render.notebook import render_rm_to_svg
from rmcompanion.render.palette import lookup_color

SAMPLE_DIR = Path(__file__).parent / "fixtures" / "rm"


def test_palette_lookup():
    # Light mode black
    r, g, b, _ = lookup_color(0, dark_mode=False)
    assert r < 50 and g < 50 and b < 50

    # Dark mode black should be light (white/zinc)
    r_d, g_d, b_d, _ = lookup_color(0, dark_mode=True)
    assert r_d > 200 and g_d > 200 and b_d > 200


def test_render_sample_rm_files():
    sample_files = [
        SAMPLE_DIR / "Color_and_tool_v3.14.4.rm",
        SAMPLE_DIR / "Bold_Heading_Bullet_Normal.rm",
        SAMPLE_DIR / "More_color_highlight_shader_v3.15.4.2.rm",
    ]

    for sample_path in sample_files:
        if not sample_path.exists():
            continue

        rm_bytes = sample_path.read_bytes()

        # Light mode
        svg_light = render_rm_to_svg(rm_bytes, dark_mode=False)
        assert svg_light.startswith("<svg")
        assert svg_light.endswith(("</svg>\n", "</svg>"))
        assert 'fill="#ffffff"' in svg_light

        # Dark mode
        svg_dark = render_rm_to_svg(rm_bytes, dark_mode=True)
        assert 'fill="#18181b"' in svg_dark

        # Verify PyMuPDF can render both to PNG without errors
        doc_l = pymupdf.open(stream=svg_light.encode("utf-8"), filetype="svg")
        pix_l = doc_l[0].get_pixmap()
        assert pix_l.width > 0 and pix_l.height > 0
        doc_l.close()

        doc_d = pymupdf.open(stream=svg_dark.encode("utf-8"), filetype="svg")
        pix_d = doc_d[0].get_pixmap()
        assert pix_d.width > 0 and pix_d.height > 0
        doc_d.close()


def test_render_typed_text_styles():
    sample_path = SAMPLE_DIR / "Bold_Heading_Bullet_Normal.rm"
    if not sample_path.exists():
        pytest.skip("Sample file not present")

    rm_bytes = sample_path.read_bytes()
    svg = render_rm_to_svg(rm_bytes, dark_mode=False)

    # Check that styles and text were emitted
    assert "class=\"rm-bold\"" in svg or "class=\"rm-heading\"" in svg
    assert "B is a letter of the alphabet" in svg


def test_render_pdf_page_image_comic_vs_text():
    import numpy as np
    from rmcompanion.render.pdf_render import render_pdf_page_image

    # 1. Text PDF (should be inverted in dark mode to dark zinc paper ~24)
    doc_t = pymupdf.open()
    pt = doc_t.new_page(width=200, height=200)
    pt.insert_text((50, 50), "Hello text world", fontsize=16, color=(0, 0, 0))
    text_pdf = doc_t.tobytes()
    doc_t.close()

    png_dark, w, h = render_pdf_page_image(text_pdf, 0, dark_mode=True)
    pix_d = pymupdf.Pixmap(png_dark)
    img_d = np.frombuffer(pix_d.samples, dtype=np.uint8).reshape((h, w, pix_d.n))
    # Paper background corner should be dark zinc (20-30)
    assert 20 <= img_d[0, 0][0] <= 30
    assert 20 <= img_d[0, 0][1] <= 30
    assert 20 <= img_d[0, 0][2] <= 30

    # 2. Comic PDF (full-bleed artwork should NOT be inverted)
    doc_c = pymupdf.open()
    pc = doc_c.new_page(width=200, height=200)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 200, 200), False)
    pix.set_rect(pix.irect, (0, 0, 255))  # pure blue comic panel
    pc.insert_image(pc.rect, pixmap=pix)
    comic_pdf = doc_c.tobytes()
    doc_c.close()

    c_dark, cw, ch = render_pdf_page_image(comic_pdf, 0, dark_mode=True)
    pix_c = pymupdf.Pixmap(c_dark)
    c_img = np.frombuffer(pix_c.samples, dtype=np.uint8).reshape((ch, cw, pix_c.n))
    # Pixel should still be blue (B > 240, R < 10, G < 10), not inverted to yellow
    assert c_img[50, 50][2] > 240
    assert c_img[50, 50][0] < 20
    assert c_img[50, 50][1] < 20


def test_render_thumbnail_dark_mode_note_vs_cover(tmp_path):
    import hashlib
    import numpy as np
    from rmcompanion.config import Settings
    from rmcompanion.render.exporter import Exporter
    from rmcompanion.store.blob_store import BlobStore
    from rmcompanion.store.db import Database

    settings = Settings(data_dir=tmp_path)
    db = Database(settings=settings)
    bs = BlobStore(settings=settings)
    exporter = Exporter(db=db, blob_store=bs, settings=settings)

    # 1. White-paper PDF note (should invert to dark ~24 in dark mode)
    doc_note = pymupdf.open()
    pn = doc_note.new_page(width=300, height=400)
    pn.insert_text((30, 50), "Meeting - Monday, Nov 2", fontsize=14, color=(0, 0, 0))
    note_pdf_bytes = doc_note.tobytes()
    doc_note.close()
    note_hash = hashlib.sha256(note_pdf_bytes).hexdigest()
    bs.put(note_hash, note_pdf_bytes)

    db.upsert_document({
        "id": "note-pdf-1",
        "doc_hash": "hash-note-1",
        "visible_name": "Meeting Note",
        "file_type": "pdf",
        "type": "DocumentType",
    })
    db.set_document_pages("hash-note-1", [{"page_idx": 0, "page_id": "p0", "deleted": False, "redir": 0}])
    db.set_document_files("hash-note-1", [{"file_id": "note-pdf-1.pdf", "blob_hash": note_hash, "size": len(note_pdf_bytes)}])

    thumb_light = exporter.render_thumbnail("note-pdf-1", dark_mode=False)
    pix_l = pymupdf.Pixmap(thumb_light)
    arr_l = np.frombuffer(pix_l.samples, dtype=np.uint8).reshape((pix_l.height, pix_l.width, pix_l.n))
    assert arr_l[5, 5][0] > 240  # white paper in light mode

    thumb_dark = exporter.render_thumbnail("note-pdf-1", dark_mode=True)
    pix_d = pymupdf.Pixmap(thumb_dark)
    arr_d = np.frombuffer(pix_d.samples, dtype=np.uint8).reshape((pix_d.height, pix_d.width, pix_d.n))
    assert 20 <= arr_d[5, 5][0] <= 30  # dark #18181b paper in dark mode

    # 2. Illustrated Book / Comic Cover with white border (should NOT invert cover art, only dim border to ~0.92)
    doc_cov = pymupdf.open()
    pc = doc_cov.new_page(width=300, height=400)
    # Draw large blue cover art with a 10px white margin
    pc.draw_rect(pymupdf.Rect(10, 10, 290, 390), color=(0.1, 0.2, 0.8), fill=(0.1, 0.2, 0.8))
    cov_pdf_bytes = doc_cov.tobytes()
    doc_cov.close()
    cov_hash = hashlib.sha256(cov_pdf_bytes).hexdigest()
    bs.put(cov_hash, cov_pdf_bytes)

    db.upsert_document({
        "id": "book-cov-1",
        "doc_hash": "hash-cov-1",
        "visible_name": "Snow Crash",
        "file_type": "pdf",
        "type": "DocumentType",
    })
    db.set_document_pages("hash-cov-1", [{"page_idx": 0, "page_id": "p0", "deleted": False, "redir": 0}])
    db.set_document_files("hash-cov-1", [{"file_id": "book-cov-1.pdf", "blob_hash": cov_hash, "size": len(cov_pdf_bytes)}])

    cov_dark = exporter.render_thumbnail("book-cov-1", dark_mode=True)
    pix_cd = pymupdf.Pixmap(cov_dark)
    arr_cd = np.frombuffer(pix_cd.samples, dtype=np.uint8).reshape((pix_cd.height, pix_cd.width, pix_cd.n))
    # Center should still be blue (B > 180, R < 50)
    mid_y, mid_x = pix_cd.height // 2, pix_cd.width // 2
    assert arr_cd[mid_y, mid_x][2] > 180
    assert arr_cd[mid_y, mid_x][0] < 50
    # Top-left white border should be dimmed (~230-238 instead of 255)
    assert 225 <= arr_cd[1, 1][0] <= 240


