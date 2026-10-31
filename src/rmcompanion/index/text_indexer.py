"""Background text indexing for typed notes, highlights, and PDF text."""

from __future__ import annotations

import io
import logging

import pymupdf
from rmscene import read_tree
from rmscene.text import TextDocument

from rmcompanion.store.blob_store import BlobStore
from rmcompanion.store.db import Database

logger = logging.getLogger(__name__)


class TextIndexer:
    """Extracts searchable text from reMarkable files into SQLite FTS5."""

    def __init__(self, db: Database, blob_store: BlobStore) -> None:
        self.db = db
        self.blob_store = blob_store

    def index_document(self, doc_id: str, doc_hash: str) -> None:
        """Extract and index all available text for a document."""
        doc = self.db.get_document(doc_id)
        if not doc or doc.get("deleted"):
            return

        files = {f["file_id"]: f["blob_hash"] for f in doc.get("files", [])}
        pages = doc.get("pages", [])

        # 1. Index PDF body text
        pdf_file = next((k for k in files if k.endswith(".pdf")), None)
        if pdf_file and self.blob_store.has(files[pdf_file]):
            try:
                pdf_bytes = self.blob_store.get(files[pdf_file])
                with pymupdf.open(stream=pdf_bytes, filetype="pdf") as pdf_doc:
                    for idx, page in enumerate(pdf_doc):
                        page_text = page.get_text()
                        if page_text.strip():
                            self.db.index_content(doc_id, idx, "pdf_text", page_text.strip())
            except Exception as e:
                logger.warning("Failed to extract PDF text for %s: %s", doc_id, e)

        # 2. Index typed text and notes from .rm files
        for page_entry in pages:
            page_idx = page_entry.get("page_idx", 0)
            page_id = page_entry.get("page_id", "")
            rm_key = f"{doc_id}/{page_id}.rm"
            rm_blob_hash = files.get(rm_key)

            if not rm_blob_hash or not self.blob_store.has(rm_blob_hash):
                continue

            try:
                rm_bytes = self.blob_store.get(rm_blob_hash)
                tree = read_tree(io.BytesIO(rm_bytes))

                if tree.root_text is not None:
                    doc_text = TextDocument.from_scene_item(tree.root_text)
                    lines = [str(p).strip() for p in doc_text.contents if str(p).strip()]
                    full_text = "\n".join(lines)
                    if full_text:
                        self.db.index_content(doc_id, page_idx, "typed_text", full_text)
            except Exception as e:
                logger.debug("Failed to index .rm text for %s page %d: %s", doc_id, page_idx, e)
