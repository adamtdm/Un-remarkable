"""Tests for SVG and PNG rendering of .rm v6 scene files."""

import base64
import struct
from pathlib import Path

import pymupdf
import pytest

from rmcompanion.render.notebook import read_page_images, render_rm_to_svg
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

    # 1. Native handwritten notebook (should render dark #18181b paper in dark mode, white in light mode)
    sample_rm = SAMPLE_DIR / "Bold_Heading_Bullet_Normal.rm"
    if sample_rm.exists():
        rm_bytes = sample_rm.read_bytes()
        rm_hash = hashlib.sha256(rm_bytes).hexdigest()
        bs.put(rm_hash, rm_bytes)

        db.upsert_document({
            "id": "notebook-note-1",
            "doc_hash": "hash-nb-1",
            "visible_name": "Meeting Notes",
            "file_type": "notebook",
            "type": "DocumentType",
        })
        db.set_document_pages("hash-nb-1", [{"page_idx": 0, "page_id": "p0", "deleted": False, "redir": 0}])
        db.set_document_files("hash-nb-1", [{"file_id": "notebook-note-1/p0.rm", "blob_hash": rm_hash, "size": len(rm_bytes)}])

        thumb_light = exporter.render_thumbnail("notebook-note-1", dark_mode=False)
        pix_l = pymupdf.Pixmap(thumb_light)
        arr_l = np.frombuffer(pix_l.samples, dtype=np.uint8).reshape((pix_l.height, pix_l.width, pix_l.n))
        assert arr_l[5, 5][0] > 240  # white paper in light mode

        thumb_dark = exporter.render_thumbnail("notebook-note-1", dark_mode=True)
        pix_d = pymupdf.Pixmap(thumb_dark)
        arr_d = np.frombuffer(pix_d.samples, dtype=np.uint8).reshape((pix_d.height, pix_d.width, pix_d.n))
        assert 20 <= arr_d[5, 5][0] <= 30  # dark #18181b paper in dark mode

    # 2. Illustrated Book / Comic Cover (should NEVER invert cover art)
    doc_cov = pymupdf.open()
    pc = doc_cov.new_page(width=300, height=400)
    # Draw large blue cover art with a white background / canvas
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
    # Center should still be blue (B > 180, R < 50), NEVER inverted to yellow
    mid_y, mid_x = pix_cd.height // 2, pix_cd.width // 2
    assert arr_cd[mid_y, mid_x][2] > 180
    assert arr_cd[mid_y, mid_x][0] < 50
    # Corner white paper should remain white / original artwork colors (not inverted to black)
    assert arr_cd[2, 2][0] > 240




# Blocks written by reMarkable 3.2x for a pasted image (here the Meeting Notes calendar icon):
# block 14 names the image file, block 15 places it on the page as a 40x40 quad.
_IMAGE_DEF_BLOCK = bytes.fromhex(
    "1c5d000000010c570000003d065f13533342bb53466167575f92fd1c330000001f0197012c2a0000002801"
    + b"6dc5c2c2-c963-4845-90bc-a9fe158ed9f9.png".hex()
    + "2c0a0000001f00002c020000001100"
)
_IMAGE_ITEM_BLOCK = bytes.fromhex(
    "1f01a1012f01a6013f00004f000054000000006c8b000000071c190000001f0199012c100000003d065f13"
    "533342bb53466167575f92fd2f0198013c4100000010008071c10000f8c100000000000000000040c74100"
    "00f8c10000803f000000000040c741000010410000803f0000803f008071c100001041000000000000803f"
    "4c19000000060000000001000000020000000200000003000000000000005f019a01"
)


def _block(block_type: int, version: int, body: bytes) -> bytes:
    return struct.pack("<IBBBB", len(body), 0, version, version, block_type) + body


def test_pasted_images_are_rendered():
    """Images pasted with the Capture tool (rmscene can't read them) are drawn under the ink."""
    rm = (SAMPLE_DIR / "Bold_Heading_Bullet_Normal.rm").read_bytes()
    rm += _block(14, 3, _IMAGE_DEF_BLOCK) + _block(15, 2, _IMAGE_ITEM_BLOCK)

    images = read_page_images(rm)
    assert len(images) == 1
    img = images[0]
    assert img["file"] == "6dc5c2c2-c963-4845-90bc-a9fe158ed9f9.png"
    assert round(img["w"]) == 40 and round(img["h"]) == 40

    png = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 4, 4), False)
    png.clear_with(0)
    svg = render_rm_to_svg(rm, images={img["file"]: png.tobytes("png")})
    assert svg.count("<image ") == 1
    assert svg.index("<image ") < svg.index('class="rm-drawing"')
    # Missing image bytes are skipped, not an error.
    assert "<image " not in render_rm_to_svg(rm, images={"other.png": b"x"})
    # Dark mode re-colours the image itself; black becomes the light ink colour.
    dark = render_rm_to_svg(rm, dark_mode=True, images={img["file"]: png.tobytes("png")})
    b64 = dark.split('href="data:image/png;base64,')[1].split('"')[0]
    pix = pymupdf.Pixmap(base64.b64decode(b64))
    assert pix.pixel(0, 0)[0] > 200


def test_highlights_are_read_from_pages(tmp_path):
    """Text highlighted on the tablet is read back, with its page and colour, and exported as Markdown."""
    import hashlib

    from rmcompanion.config import Settings
    from rmcompanion.reading import document_highlights, highlights_markdown
    from rmcompanion.store.blob_store import BlobStore

    store = BlobStore(settings=Settings(data_dir=tmp_path))
    files = []
    for name, data in (("book.pdf", b"%PDF-1.4"), ("book/p2.rm", (SAMPLE_DIR / "Wikipedia_highlighted_p1.rm").read_bytes())):
        h = hashlib.sha256(data).hexdigest()
        store.put(h, data)
        files.append({"file_id": name, "blob_hash": h})
    doc = {"id": "book", "files": files, "pages": [{"page_id": "p1"}, {"page_id": "p2"}]}

    found = document_highlights(doc, store)
    assert found and all(h["page"] == 1 and h["text"] and h["color"].startswith("rgba(") for h in found)
    md = highlights_markdown([("Wiki", found)])
    assert md.startswith("# Highlights\n\n## Wiki") and "— page 2" in md
