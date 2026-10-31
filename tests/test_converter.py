"""Tests for the Paper Pro comic and document converter."""

import pymupdf

from rmcompanion.converter.engine import QUALITY_PROFILES, ConverterEngine


def create_dummy_pdf(num_pages: int = 3, has_spread: bool = False) -> bytes:
    doc = pymupdf.open()
    for i in range(num_pages):
        width, height = (800, 1200) if not (has_spread and i == 1) else (1600, 1000)
        page = doc.new_page(width=width, height=height)
        # Draw some content
        page.draw_rect([50, 50, width - 50, height - 50], color=(0, 0, 1), fill=(0.9, 0.9, 0.9))
        page.insert_text((100, 100), f"Page {i + 1} dummy text", fontsize=24)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_converter_profiles():
    assert len(QUALITY_PROFILES) == 5
    assert QUALITY_PROFILES[3].name == "Balanced"
    assert QUALITY_PROFILES[3].max_height == 2160
    assert QUALITY_PROFILES[3].max_width == 1620


def test_converter_sync_execution(tmp_path):
    converter = ConverterEngine()
    pdf_in = create_dummy_pdf(num_pages=3, has_spread=True)

    # Convert at stop 1 (Smallest)
    out_bytes_1 = converter.convert_sync(
        input_bytes=pdf_in,
        input_type="pdf",
        quality_stop=1,
        split_spreads=False,
    )
    assert len(out_bytes_1) > 0

    # Verify output is a valid PDF
    doc_out = pymupdf.open(stream=out_bytes_1, filetype="pdf")
    assert len(doc_out) == 3
    # Check that image was inserted into the page
    assert len(doc_out[0].get_images()) >= 1
    doc_out.close()

    # Convert with split_spreads enabled: the spread page should become 2 pages
    out_bytes_split = converter.convert_sync(
        input_bytes=pdf_in,
        input_type="pdf",
        quality_stop=3,
        split_spreads=True,
    )
    doc_split = pymupdf.open(stream=out_bytes_split, filetype="pdf")
    # 1 normal + 2 split from spread + 1 normal = 4 pages
    assert len(doc_split) == 4
    doc_split.close()
