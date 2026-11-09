"""Reading aids for the web reader: a book's table of contents and its highlights."""

from __future__ import annotations

import io
import logging
from typing import Any

import pymupdf
from rmscene import read_tree
from rmscene import scene_items as si

from rmcompanion.render.palette import format_rgba, lookup_color
from rmcompanion.store.blob_store import BlobStore

logger = logging.getLogger(__name__)


def _files(doc: dict[str, Any]) -> dict[str, str]:
    return {f["file_id"]: f["blob_hash"] for f in doc.get("files", [])}


def table_of_contents(doc: dict[str, Any], blob_store: BlobStore) -> list[dict[str, Any]]:
    """The PDF/EPUB outline as [{level, title, page}], with `page` as a reader page index.

    reMarkable lets you insert note pages into a PDF, so a PDF page is found through each
    page's `redir` (the PDF page it shows) rather than assumed to be the same index.
    """
    files = _files(doc)
    source = next((k for k in files if k.endswith(".pdf")), None) or next(
        (k for k in files if k.endswith(".epub")), None
    )
    if not source or not blob_store.has(files[source]):
        return []
    try:
        with pymupdf.open(blob_store.get_path(files[source]), filetype=source.rsplit(".", 1)[1]) as pdf:
            outline = pdf.get_toc(simple=True)
    except Exception as e:
        logger.warning("Could not read the outline of %s: %s", doc.get("id"), e)
        return []

    by_pdf_page = {}
    for i, p in enumerate(doc.get("pages", [])):
        redir = p.get("redir", -1)
        if redir is not None and redir >= 0 and redir not in by_pdf_page:
            by_pdf_page[redir] = i
    return [
        {"level": level, "title": title.strip(), "page": by_pdf_page.get(page - 1, max(page - 1, 0))}
        for level, title, page in outline
        if title.strip()
    ]


def document_highlights(doc: dict[str, Any], blob_store: BlobStore) -> list[dict[str, Any]]:
    """Text highlighted on the tablet, in page order: [{page, text, color}]."""
    files = _files(doc)
    out: list[dict[str, Any]] = []
    # Only PDFs and EPUBs have text to highlight; notebook pages are slow to parse and have none.
    if not any(k.endswith((".pdf", ".epub")) for k in files):
        return out
    for idx, page in enumerate(doc.get("pages", [])):
        blob = files.get(f"{doc['id']}/{page.get('page_id', '')}.rm")
        if not blob or not blob_store.has(blob):
            continue
        try:
            tree = read_tree(io.BytesIO(blob_store.get(blob)))
            ranges = [item for item in tree.walk() if isinstance(item, si.GlyphRange)]
        except Exception as e:
            logger.debug("Skipping unreadable page %d of %s: %s", idx, doc.get("id"), e)
            continue
        # Highlights are stored in the order they were made; show them top to bottom.
        ranges.sort(key=lambda g: (g.rectangles[0].y, g.rectangles[0].x) if g.rectangles else (0, 0))
        for g in ranges:
            text = (g.text or "").strip()
            if text:
                rgba = getattr(g, "color_rgba", None)
                # Plain highlighter strokes carry no colour of their own: show them yellow.
                color = si.PenColor.YELLOW.value if g.color == si.PenColor.HIGHLIGHT and not rgba else g.color.value
                r, gr, b, _ = lookup_color(color, rgba)
                out.append({"page": idx, "text": text, "color": format_rgba(r, gr, b)})
    return out


def highlights_markdown(books: list[tuple[str, list[dict[str, Any]]]]) -> str:
    """Highlights as Markdown: one section per book, each highlight a quote with its page."""
    parts = []
    for title, highlights in books:
        if not highlights:
            continue
        parts.append(f"## {title}\n")
        parts.extend(f"> {h['text']}\n\n— page {h['page'] + 1}\n" for h in highlights)
    return "# Highlights\n\n" + "\n".join(parts) if parts else "# Highlights\n\nNo highlights yet.\n"
