"""Notebook editor for creating and modifying reMarkable notebooks and typed text."""

from __future__ import annotations

import hashlib
import io
import json
import logging
import time
import uuid
from typing import Any

import rmscene
from rmscene import CrdtId, CrdtSequence, CrdtSequenceItem, LwwValue, RootTextBlock
from rmscene import scene_items as si
from rmscene.text import TextDocument

from rmcompanion.cloud.index import Entry, compute_doc_index_hash
from rmcompanion.intelligence.task_extractor import (
    TASKS_NOTEBOOK_STATE_KEY,
    TaskExtractor,
)
from rmcompanion.store.blob_store import BlobStore
from rmcompanion.store.db import Database

logger = logging.getLogger(__name__)

def page_order_key(idx: int) -> str:
    """Page position string for .content cPages. The tablet orders pages by sorting these as
    text, so they must have a fixed width: "ba10" would sort before "ba2"."""
    letters = ""
    for _ in range(3):
        letters = chr(ord("a") + idx % 26) + letters
        idx //= 26
    return "b" + letters


# Typed lines that fit on one tablet page with room for long tasks to wrap.
TASK_PAGE_LINES = 18


def layout_task_pages(title: str, tasks: list[dict[str, Any]], max_lines: int = TASK_PAGE_LINES) -> list[str]:
    """Lay out open tasks as typed-text pages, grouped under the notebook each came from.

    A group that runs past the end of a page continues on the next page under a repeated heading.
    """
    def _key(t: dict[str, Any]) -> tuple[int, str, float]:
        name = t.get("doc_name") or ""
        return (0 if not name else 1, name.lower(), t.get("created_at") or 0.0)

    pages: list[list[str]] = [[]]
    last_source: str | None = None
    for t in sorted(tasks, key=_key):
        source = t.get("doc_name") or "Captured"
        page = pages[-1]
        new_group = source != last_source or not page
        needed = 1 + (1 if new_group else 0) + (1 if new_group and page else 0)
        if page and len(page) + needed > max_lines:
            pages.append([])
            page = pages[-1]
            new_group = True
        if new_group:
            if page:
                page.append("")
            page.append(source)
        page.append(f"[ ] {t.get('clean_text', '')}")
        last_source = source

    if not tasks:
        pages[0].append("No open tasks.")
    return [
        f"{title} - {len(tasks)} open - page {i}/{len(pages)}\n\n" + "\n".join(lines)
        for i, lines in enumerate(pages, 1)
    ]


def extract_page_typed_text(rm_bytes: bytes) -> str:
    """Extract plain typed text from a .rm v6 binary file."""
    if not rm_bytes or not rm_bytes.startswith(b"reMarkable .lines file, version=6"):
        return ""
    try:
        tree = rmscene.read_tree(io.BytesIO(rm_bytes))
        if tree.root_text is not None:
            doc = TextDocument.from_scene_item(tree.root_text)
            return "\n".join("".join(s.s for s in p.contents) for p in doc.contents)
    except Exception as exc:
        logger.debug("Failed to extract typed text from rm bytes: %s", exc)
    return ""


def build_rm_text_blocks(text: str) -> bytes:
    """Generate a clean reMarkable v6 binary file with typed text."""
    buf = io.BytesIO()
    rmscene.write_blocks(buf, rmscene.simple_text_document(text))
    return buf.getvalue()


def update_rm_text_in_bytes(existing_bytes: bytes, new_text: str) -> bytes:
    """Update or insert typed text in an existing .rm binary file, preserving strokes."""
    if not existing_bytes or not existing_bytes.startswith(b"reMarkable .lines file, version=6"):
        return build_rm_text_blocks(new_text)

    try:
        blocks = list(rmscene.read_blocks(io.BytesIO(existing_bytes)))
    except Exception as exc:
        logger.warning("Corrupted .rm file, recreating simple text document: %s", exc)
        return build_rm_text_blocks(new_text)

    new_blocks = []
    found_root_text = False

    new_text_item = si.Text(
        items=CrdtSequence([
            CrdtSequenceItem(
                item_id=CrdtId(1, 16),
                left_id=CrdtId(0, 0),
                right_id=CrdtId(0, 0),
                deleted_length=0,
                value=new_text,
            )
        ]),
        styles={
            CrdtId(0, 0): LwwValue(timestamp=CrdtId(1, 15), value=si.ParagraphStyle.PLAIN),
        },
        pos_x=-468.0,
        pos_y=234.0,
        width=936.0,
    )

    for b in blocks:
        if isinstance(b, RootTextBlock):
            found_root_text = True
            new_blocks.append(RootTextBlock(block_id=b.block_id, value=new_text_item))
        elif isinstance(b, rmscene.PageInfoBlock):
            new_blocks.append(rmscene.PageInfoBlock(
                loads_count=b.loads_count + 1,
                merges_count=b.merges_count,
                text_chars_count=len(new_text) + 1,
                text_lines_count=new_text.count("\n") + 1,
                type_folio_use_count=b.type_folio_use_count,
            ))
        else:
            new_blocks.append(b)

    if not found_root_text:
        # Document had strokes but no RootTextBlock, append one
        new_blocks.append(RootTextBlock(block_id=CrdtId(0, 0), value=new_text_item))

    out_buf = io.BytesIO()
    rmscene.write_blocks(out_buf, new_blocks)
    return out_buf.getvalue()


class NotebookEditor:
    """Manages creation, text editing, and markdown importing of reMarkable notebooks."""

    def __init__(
        self,
        db: Database,
        blob_store: BlobStore,
        task_extractor: TaskExtractor | None = None,
    ) -> None:
        self.db = db
        self.blob_store = blob_store
        self.task_extractor = task_extractor

    def create_notebook(
        self,
        title: str,
        initial_text: str = "",
        parent_id: str = "",
        pages_content: list[str] | None = None,
        doc_id: str = "",
    ) -> dict[str, Any]:
        """Create a native reMarkable notebook with one or more pages.

        Pass an existing doc_id to rebuild that notebook in place (same ID locally and in the cloud).
        """
        now_ms = str(int(time.time() * 1000))
        doc_id = doc_id or str(uuid.uuid4())

        # Determine page contents
        if pages_content is not None and len(pages_content) > 0:
            contents = pages_content
        else:
            contents = [initial_text]

        page_ids: list[str] = [str(uuid.uuid4()) for _ in contents]
        files_meta: list[dict[str, Any]] = []
        doc_pages_meta: list[dict[str, Any]] = []
        c_pages_list: list[dict[str, Any]] = []

        total_bytes = 0

        # Create .rm files for each page
        for idx, (p_id, text) in enumerate(zip(page_ids, contents)):
            rm_bytes = build_rm_text_blocks(text)
            rm_hash = hashlib.sha256(rm_bytes).hexdigest()
            self.blob_store.put(rm_hash, rm_bytes)
            total_bytes += len(rm_bytes)

            file_key = f"{doc_id}/{p_id}.rm"
            files_meta.append({
                "file_id": file_key,
                "blob_hash": rm_hash,
                "file_type": "rm",
                "size": len(rm_bytes),
            })
            doc_pages_meta.append({
                "page_idx": idx,
                "page_id": p_id,
                "deleted": False,
                "redir": -1,
            })
            c_pages_list.append({
                "id": p_id,
                "idx": {"timestamp": f"1:{idx + 1}", "value": page_order_key(idx)},
                "template": {"timestamp": "1:1", "value": "P Blank"},
            })

        # Create .pagedata file
        pagedata_content = "\n".join(["P Blank"] * len(page_ids)) + "\n"
        pagedata_bytes = pagedata_content.encode("utf-8")
        pagedata_hash = hashlib.sha256(pagedata_bytes).hexdigest()
        self.blob_store.put(pagedata_hash, pagedata_bytes)
        files_meta.append({
            "file_id": f"{doc_id}.pagedata",
            "blob_hash": pagedata_hash,
            "file_type": "pagedata",
            "size": len(pagedata_bytes),
        })

        # Create .content file
        content_dict = {
            "cPages": {
                "lastOpened": {"timestamp": "1:1", "value": page_ids[0]},
                "original": {"timestamp": "0:0", "value": -1},
                "pages": c_pages_list,
            },
            "crdt": True,
            "dummyDocument": False,
            "extraMetadata": {},
            "fileType": "notebook",
            "fontName": "",
            "formatVersion": 2,
            "lineHeight": -1,
            "margins": 125,
            "orientation": "portrait",
            "originalPageCount": -1,
            "pageCount": len(page_ids),
            "pages": page_ids,
            "pageTags": [],
            "sizeInBytes": str(total_bytes),
            "textAlignment": "left",
            "textScale": 1,
        }
        content_bytes = json.dumps(content_dict, indent=2).encode("utf-8")
        content_hash = hashlib.sha256(content_bytes).hexdigest()
        self.blob_store.put(content_hash, content_bytes)
        files_meta.append({
            "file_id": f"{doc_id}.content",
            "blob_hash": content_hash,
            "file_type": "content",
            "size": len(content_bytes),
        })

        # Create .metadata file
        meta_dict = {
            "createdTime": now_ms,
            "lastModified": now_ms,
            "lastOpened": now_ms,
            "lastOpenedPage": 0,
            "new": False,
            "parent": parent_id or "",
            "pinned": False,
            "source": "",
            "type": "DocumentType",
            "visibleName": title,
        }
        meta_bytes = json.dumps(meta_dict, indent=2).encode("utf-8")
        meta_hash = hashlib.sha256(meta_bytes).hexdigest()
        self.blob_store.put(meta_hash, meta_bytes)
        files_meta.append({
            "file_id": f"{doc_id}.metadata",
            "blob_hash": meta_hash,
            "file_type": "metadata",
            "size": len(meta_bytes),
        })

        # Compute document index hash
        entries = [
            Entry(
                hash=f["blob_hash"],
                type="0",
                doc_id=f["file_id"],
                subfiles=0,
                size=f["size"],
            )
            for f in files_meta
        ]
        doc_hash = compute_doc_index_hash(entries)

        # Record in database
        doc_record = {
            "id": doc_id,
            "visible_name": title,
            "type": "DocumentType",
            "parent_id": parent_id or "",
            "last_modified": now_ms,
            "last_opened": now_ms,
            "last_opened_page": 0,
            "pinned": False,
            "deleted": False,
            "file_type": "notebook",
            "page_count": len(page_ids),
            "doc_hash": doc_hash,
        }
        self.db.upsert_document(doc_record)
        self.db.set_document_files(doc_hash, files_meta)
        self.db.set_document_pages(doc_hash, doc_pages_meta)

        # Index typed content for full-text search and extract tasks
        for idx, text in enumerate(contents):
            if text.strip():
                self.db.index_content(doc_id, idx, "typed", text)
                if self.task_extractor:
                    self.task_extractor.extract_from_typed_page(doc_id, idx, text)

        logger.info("Created new notebook %s (%s) with %d pages", title, doc_id, len(page_ids))
        return {
            "id": doc_id,
            "visible_name": title,
            "page_count": len(page_ids),
            "doc_hash": doc_hash,
            "parent_id": parent_id or "",
        }

    def get_page_typed_text(self, doc_id: str, page_idx: int = 0) -> str:
        """Fetch existing typed text for a page in a notebook."""
        doc = self.db.get_document(doc_id)
        if not doc:
            raise FileNotFoundError(f"Document {doc_id} not found")

        pages = doc.get("pages", [])
        if not pages or page_idx < 0 or page_idx >= len(pages):
            return ""

        page_id = pages[page_idx].get("page_id", "")
        file_map = {f["file_id"]: f["blob_hash"] for f in doc.get("files", [])}
        rm_key = f"{doc_id}/{page_id}.rm"
        blob_hash = file_map.get(rm_key)

        if not blob_hash or not self.blob_store.has(blob_hash):
            return ""

        raw_rm = self.blob_store.get(blob_hash)
        return extract_page_typed_text(raw_rm)

    def update_page_typed_text(
        self,
        doc_id: str,
        page_idx: int,
        text: str,
    ) -> dict[str, Any]:
        """Update typed text of a notebook page, merging with strokes."""
        doc = self.db.get_document(doc_id)
        if not doc:
            raise FileNotFoundError(f"Document {doc_id} not found")

        pages = doc.get("pages", [])
        if not pages or page_idx < 0 or page_idx >= len(pages):
            raise IndexError(f"Page index {page_idx} out of range for doc {doc_id}")

        page_id = pages[page_idx].get("page_id", "")
        file_map = {f["file_id"]: f for f in doc.get("files", [])}
        rm_key = f"{doc_id}/{page_id}.rm"

        existing_bytes = b""
        if rm_key in file_map and self.blob_store.has(file_map[rm_key]["blob_hash"]):
            existing_bytes = self.blob_store.get(file_map[rm_key]["blob_hash"])

        new_rm_bytes = update_rm_text_in_bytes(existing_bytes, text)
        new_rm_hash = hashlib.sha256(new_rm_bytes).hexdigest()
        self.blob_store.put(new_rm_hash, new_rm_bytes)

        now_ms = str(int(time.time() * 1000))

        # Update metadata file
        meta_key = f"{doc_id}.metadata"
        meta_dict = {
            "createdTime": doc.get("last_modified", now_ms),
            "lastModified": now_ms,
            "lastOpened": now_ms,
            "lastOpenedPage": page_idx,
            "new": False,
            "parent": doc.get("parent_id", ""),
            "pinned": doc.get("pinned", False),
            "source": "",
            "type": "DocumentType",
            "visibleName": doc.get("visible_name", "Notebook"),
        }
        if meta_key in file_map and self.blob_store.has(file_map[meta_key]["blob_hash"]):
            try:
                meta_dict.update(json.loads(self.blob_store.get(file_map[meta_key]["blob_hash"]).decode("utf-8")))
            except Exception as e:
                logger.warning("Unreadable metadata for %s, rewriting it: %s", doc_id, e)
        meta_dict["lastModified"] = now_ms
        meta_dict["lastOpened"] = now_ms
        meta_dict["lastOpenedPage"] = page_idx
        new_meta_bytes = json.dumps(meta_dict, indent=2).encode("utf-8")
        new_meta_hash = hashlib.sha256(new_meta_bytes).hexdigest()
        self.blob_store.put(new_meta_hash, new_meta_bytes)

        # Build updated files list
        updated_files: list[dict[str, Any]] = []
        for f_id, f_data in file_map.items():
            if f_id == rm_key:
                updated_files.append({
                    "file_id": rm_key,
                    "blob_hash": new_rm_hash,
                    "file_type": "rm",
                    "size": len(new_rm_bytes),
                })
            elif f_id == meta_key:
                updated_files.append({
                    "file_id": meta_key,
                    "blob_hash": new_meta_hash,
                    "file_type": "metadata",
                    "size": len(new_meta_bytes),
                })
            else:
                updated_files.append(f_data)

        # If rm_key was somehow not in file_map, add it
        if not any(f["file_id"] == rm_key for f in updated_files):
            updated_files.append({
                "file_id": rm_key,
                "blob_hash": new_rm_hash,
                "file_type": "rm",
                "size": len(new_rm_bytes),
            })

        # Compute new doc_hash
        entries = [
            Entry(
                hash=f["blob_hash"],
                type="0",
                doc_id=f["file_id"],
                subfiles=0,
                size=f["size"],
            )
            for f in updated_files
        ]
        new_doc_hash = compute_doc_index_hash(entries)

        # Update DB records
        doc["last_modified"] = now_ms
        doc["last_opened"] = now_ms
        doc["last_opened_page"] = page_idx
        doc["doc_hash"] = new_doc_hash
        self.db.upsert_document(doc)
        self.db.set_document_files(new_doc_hash, updated_files)
        self.db.set_document_pages(new_doc_hash, pages)

        # Re-index full-text search and extract tasks
        self.db.index_content(doc_id, page_idx, "typed", text)
        if self.task_extractor and text.strip():
            self.task_extractor.extract_from_typed_page(doc_id, page_idx, text)

        logger.info("Updated typed text for doc %s page %d", doc_id, page_idx)
        return {
            "id": doc_id,
            "page_idx": page_idx,
            "doc_hash": new_doc_hash,
            "last_modified": now_ms,
        }

    def update_document_position(
        self,
        doc_id: str,
        page_idx: int,
    ) -> dict[str, Any]:
        """Update last opened page and timestamp for a document in SQLite and local metadata/content blobs."""
        doc = self.db.get_document(doc_id)
        if not doc:
            raise FileNotFoundError(f"Document {doc_id} not found")

        pages = doc.get("pages", [])
        total_pages = doc.get("page_count", len(pages)) or 1
        page_idx = max(0, min(page_idx, total_pages - 1)) if total_pages > 0 else 0

        now_ms = str(int(time.time() * 1000))
        file_map = {f["file_id"]: f for f in doc.get("files", [])}

        meta_key = f"{doc_id}.metadata"
        content_key = f"{doc_id}.content"

        updated_files: list[dict[str, Any]] = []
        new_meta_hash = None
        new_meta_bytes = None
        new_content_hash = None
        new_content_bytes = None

        # 1. Update .metadata
        if meta_key in file_map and self.blob_store.has(file_map[meta_key]["blob_hash"]):
            try:
                meta_dict = json.loads(self.blob_store.get(file_map[meta_key]["blob_hash"]).decode("utf-8"))
            except Exception:
                meta_dict = {}
            meta_dict["lastOpenedPage"] = page_idx
            meta_dict["lastOpened"] = now_ms
            new_meta_bytes = json.dumps(meta_dict, indent=2).encode("utf-8")
            new_meta_hash = hashlib.sha256(new_meta_bytes).hexdigest()
            self.blob_store.put(new_meta_hash, new_meta_bytes)

        # 2. Update .content if present
        if content_key in file_map and self.blob_store.has(file_map[content_key]["blob_hash"]):
            try:
                content_dict = json.loads(self.blob_store.get(file_map[content_key]["blob_hash"]).decode("utf-8"))
                page_id = ""
                if 0 <= page_idx < len(pages):
                    page_id = pages[page_idx].get("page_id", "")
                elif "cPages" in content_dict and isinstance(content_dict["cPages"], dict):
                    c_pages = content_dict["cPages"].get("pages", [])
                    if 0 <= page_idx < len(c_pages):
                        cp = c_pages[page_idx]
                        page_id = cp.get("id", "") if isinstance(cp, dict) else str(cp)
                elif (
                    "pages" in content_dict
                    and isinstance(content_dict["pages"], list)
                    and 0 <= page_idx < len(content_dict["pages"])
                ):
                    page_id = str(content_dict["pages"][page_idx])

                if "cPages" in content_dict and isinstance(content_dict["cPages"], dict) and page_id:
                    if "lastOpened" not in content_dict["cPages"] or not isinstance(content_dict["cPages"]["lastOpened"], dict):
                        content_dict["cPages"]["lastOpened"] = {}
                    content_dict["cPages"]["lastOpened"]["value"] = page_id
                    content_dict["cPages"]["lastOpened"]["timestamp"] = f"1:{page_idx + 1}"

                new_content_bytes = json.dumps(content_dict, indent=2).encode("utf-8")
                new_content_hash = hashlib.sha256(new_content_bytes).hexdigest()
                self.blob_store.put(new_content_hash, new_content_bytes)
            except Exception as e:
                logger.warning("Could not update .content for position on doc %s: %s", doc_id, e)

        # Rebuild files list
        for f_id, f_data in file_map.items():
            if f_id == meta_key and new_meta_hash and new_meta_bytes:
                updated_files.append({
                    "file_id": meta_key,
                    "blob_hash": new_meta_hash,
                    "file_type": "metadata",
                    "size": len(new_meta_bytes),
                })
            elif f_id == content_key and new_content_hash and new_content_bytes:
                updated_files.append({
                    "file_id": content_key,
                    "blob_hash": new_content_hash,
                    "file_type": "content",
                    "size": len(new_content_bytes),
                })
            else:
                updated_files.append(f_data)

        # Compute new doc_hash if files exist
        if updated_files:
            entries = [
                Entry(
                    hash=f["blob_hash"],
                    type="0",
                    doc_id=f["file_id"],
                    subfiles=0,
                    size=f["size"],
                )
                for f in updated_files
            ]
            new_doc_hash = compute_doc_index_hash(entries)
        else:
            new_doc_hash = doc.get("doc_hash", "")

        # Update doc record in database
        doc["last_opened_page"] = page_idx
        doc["last_opened"] = now_ms
        if new_doc_hash:
            doc["doc_hash"] = new_doc_hash
        self.db.upsert_document(doc)
        if new_doc_hash and updated_files:
            self.db.set_document_files(new_doc_hash, updated_files)
            self.db.set_document_pages(new_doc_hash, pages)

        logger.info("Updated position for doc %s to page %d", doc_id, page_idx)
        return {
            "id": doc_id,
            "last_opened_page": page_idx,
            "last_opened": now_ms,
            "doc_hash": new_doc_hash,
        }

    def append_task_to_tasks_notebook(
        self,
        task_text: str,
        notebook_title: str = "Tasks",
    ) -> dict[str, Any]:
        """Record a captured task and rebuild the consolidated Tasks notebook."""
        clean = task_text.strip()
        now = time.time()
        self.db.upsert_task({
            "id": f"task_{uuid.uuid4().hex[:12]}",
            "doc_id": "",
            "page_idx": 0,
            "raw_text": clean,
            "clean_text": clean,
            "status": "open",
            "marker_type": "star",
            "fingerprint": hashlib.sha256(f"captured:{clean.lower()}".encode()).hexdigest(),
            "created_at": now,
        })
        res = self.sync_tasks_to_notebook(notebook_title)
        res["task_line"] = f"[ ] {clean}"
        return res

    def append_note_to_notebook(
        self,
        text: str,
        notebook_title: str = "Quick Notes",
        parent_id: str = "",
    ) -> dict[str, Any]:
        """Append a dated note entry to a notebook (creating it if not present)."""
        import datetime
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"\n\n---\n**{now_str}**\n{text.strip()}\n"

        docs = self.db.list_documents(include_deleted=False)
        target_doc = next(
            (d for d in docs if d.get("visible_name") == notebook_title and d.get("file_type") == "notebook"),
            None,
        )

        if not target_doc:
            initial = f"# {notebook_title}\n{entry}"
            return self.create_notebook(title=notebook_title, initial_text=initial, parent_id=parent_id)

        doc_id = target_doc["id"]
        current_text = self.get_page_typed_text(doc_id, 0)
        updated_text = (current_text or f"# {notebook_title}").rstrip() + entry
        self.update_page_typed_text(doc_id, 0, updated_text)
        return {
            "id": doc_id,
            "visible_name": notebook_title,
            "entry": entry,
        }

    def sync_tasks_to_notebook(self, notebook_title: str = "Tasks") -> dict[str, Any]:
        """Rebuild the single consolidated Tasks notebook from all open tasks.

        The notebook keeps one stable ID, so the cloud copy is updated in place rather than
        duplicated. It is a generated view: handwriting added to it on the tablet is replaced
        on the next rebuild. Complete tasks in the web UI or by crossing them out at the source.
        """
        doc_id = self._tasks_notebook_id(notebook_title)
        # Set before writing so the task extractor skips our own generated lines.
        self.db.set_state(TASKS_NOTEBOOK_STATE_KEY, doc_id)

        open_tasks = [t for t in self.db.list_tasks(status="open") if t.get("doc_id") != doc_id]
        pages = layout_task_pages(notebook_title, open_tasks)
        with self.db.connect() as conn:  # drop index rows for pages that no longer exist
            conn.execute("DELETE FROM search_index WHERE doc_id = ? AND source != 'title'", (doc_id,))
        res = self.create_notebook(title=notebook_title, parent_id="", pages_content=pages, doc_id=doc_id)
        return {
            "id": doc_id,
            "visible_name": notebook_title,
            "task_count": len(open_tasks),
            "page_count": res["page_count"],
        }

    def _tasks_notebook_id(self, notebook_title: str) -> str:
        """Reuse the known Tasks notebook, else adopt a local one with that title, else a new ID."""
        known = self.db.get_state(TASKS_NOTEBOOK_STATE_KEY, "")
        known_doc = self.db.get_document(known) if known else None
        if known_doc and not known_doc.get("deleted"):
            return known
        existing = next(
            (
                d for d in self.db.list_documents(include_deleted=False)
                if d.get("visible_name") == notebook_title and d.get("file_type") == "notebook"
            ),
            None,
        )
        return existing["id"] if existing else str(uuid.uuid4())

    def import_markdown(
        self,
        title: str,
        markdown_content: str,
        parent_id: str = "",
    ) -> dict[str, Any]:
        """Import markdown content, splitting by page breaks ('---') if present."""
        # Check for explicit page separators
        parts = [p.strip() for p in markdown_content.split("\n---\n") if p.strip()]
        if not parts:
            parts = [markdown_content.strip() or title]

        return self.create_notebook(
            title=title,
            parent_id=parent_id,
            pages_content=parts,
        )

    def import_pdf_file(
        self,
        title: str,
        pdf_bytes: bytes,
        parent_id: str = "",
    ) -> dict[str, Any]:
        """Import a PDF document into the reMarkable library."""
        import pymupdf
        with pymupdf.open(stream=pdf_bytes, filetype="pdf") as pdf_doc:
            page_count = len(pdf_doc)

        now_ms = str(int(time.time() * 1000))
        doc_id = str(uuid.uuid4())
        page_ids = [str(uuid.uuid4()) for _ in range(page_count)]

        files_meta: list[dict[str, Any]] = []
        doc_pages_meta: list[dict[str, Any]] = []
        c_pages_list: list[dict[str, Any]] = []

        # 1. Store PDF blob
        pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
        self.blob_store.put(pdf_hash, pdf_bytes)
        files_meta.append({
            "file_id": f"{doc_id}.pdf",
            "blob_hash": pdf_hash,
            "file_type": "pdf",
            "size": len(pdf_bytes),
        })

        for idx, p_id in enumerate(page_ids):
            doc_pages_meta.append({
                "page_idx": idx,
                "page_id": p_id,
                "deleted": False,
                "redir": idx,
            })
            c_pages_list.append({
                "id": p_id,
                "idx": {"timestamp": f"1:{idx + 1}", "value": page_order_key(idx)},
                "redir": {"timestamp": "1:1", "value": idx},
                "template": {"timestamp": "1:1", "value": "P Blank"},
            })

        # 2. Store .pagedata
        pagedata_content = "\n".join(["P Blank"] * page_count) + "\n"
        pagedata_bytes = pagedata_content.encode("utf-8")
        pagedata_hash = hashlib.sha256(pagedata_bytes).hexdigest()
        self.blob_store.put(pagedata_hash, pagedata_bytes)
        files_meta.append({
            "file_id": f"{doc_id}.pagedata",
            "blob_hash": pagedata_hash,
            "file_type": "pagedata",
            "size": len(pagedata_bytes),
        })

        # 3. Store .content
        content_dict = {
            "cPages": {
                "lastOpened": {"timestamp": "1:1", "value": page_ids[0] if page_ids else ""},
                "original": {"timestamp": "0:0", "value": -1},
                "pages": c_pages_list,
            },
            "crdt": True,
            "dummyDocument": False,
            "extraMetadata": {},
            "fileType": "pdf",
            "formatVersion": 2,
            "lineHeight": -1,
            "margins": 125,
            "orientation": "portrait",
            "originalPageCount": page_count,
            "pageCount": page_count,
            "pages": page_ids,
            "pageTags": [],
            "sizeInBytes": str(len(pdf_bytes)),
            "textAlignment": "left",
            "textScale": 1,
        }
        content_bytes = json.dumps(content_dict, indent=2).encode("utf-8")
        content_hash = hashlib.sha256(content_bytes).hexdigest()
        self.blob_store.put(content_hash, content_bytes)
        files_meta.append({
            "file_id": f"{doc_id}.content",
            "blob_hash": content_hash,
            "file_type": "content",
            "size": len(content_bytes),
        })

        # 4. Store .metadata
        meta_dict = {
            "createdTime": now_ms,
            "lastModified": now_ms,
            "lastOpened": now_ms,
            "lastOpenedPage": 0,
            "new": True,
            "parent": parent_id or "",
            "pinned": False,
            "source": "",
            "type": "DocumentType",
            "visibleName": title,
        }
        meta_bytes = json.dumps(meta_dict, indent=2).encode("utf-8")
        meta_hash = hashlib.sha256(meta_bytes).hexdigest()
        self.blob_store.put(meta_hash, meta_bytes)
        files_meta.append({
            "file_id": f"{doc_id}.metadata",
            "blob_hash": meta_hash,
            "file_type": "metadata",
            "size": len(meta_bytes),
        })

        # Compute doc_hash
        entries = [
            Entry(
                hash=f["blob_hash"],
                type="0",
                doc_id=f["file_id"],
                subfiles=0,
                size=f["size"],
            )
            for f in files_meta
        ]
        doc_hash = compute_doc_index_hash(entries)

        doc_record = {
            "id": doc_id,
            "visible_name": title,
            "type": "DocumentType",
            "parent_id": parent_id or "",
            "last_modified": now_ms,
            "last_opened": now_ms,
            "last_opened_page": 0,
            "pinned": False,
            "deleted": False,
            "file_type": "pdf",
            "page_count": page_count,
            "doc_hash": doc_hash,
        }
        self.db.upsert_document(doc_record)
        self.db.set_document_files(doc_hash, files_meta)
        self.db.set_document_pages(doc_hash, doc_pages_meta)

        logger.info("Imported PDF document %s (%s) with %d pages", title, doc_id, page_count)
        return {
            "id": doc_id,
            "visible_name": title,
            "page_count": page_count,
            "doc_hash": doc_hash,
            "parent_id": parent_id or "",
            "file_type": "pdf",
        }

    def import_epub_file(
        self,
        title: str,
        epub_bytes: bytes,
        parent_id: str = "",
    ) -> dict[str, Any]:
        """Import an EPUB document into the reMarkable library."""
        import pymupdf
        try:
            with pymupdf.open(stream=epub_bytes, filetype="epub") as ep_doc:
                page_count = len(ep_doc)
        except Exception:
            page_count = 1

        now_ms = str(int(time.time() * 1000))
        doc_id = str(uuid.uuid4())
        page_ids = [str(uuid.uuid4()) for _ in range(max(1, page_count))]

        files_meta: list[dict[str, Any]] = []
        doc_pages_meta: list[dict[str, Any]] = []
        c_pages_list: list[dict[str, Any]] = []

        # 1. Store EPUB blob
        epub_hash = hashlib.sha256(epub_bytes).hexdigest()
        self.blob_store.put(epub_hash, epub_bytes)
        files_meta.append({
            "file_id": f"{doc_id}.epub",
            "blob_hash": epub_hash,
            "file_type": "epub",
            "size": len(epub_bytes),
        })

        for idx, p_id in enumerate(page_ids):
            doc_pages_meta.append({
                "page_idx": idx,
                "page_id": p_id,
                "deleted": False,
                "redir": -1,
            })
            c_pages_list.append({
                "id": p_id,
                "idx": {"timestamp": f"1:{idx + 1}", "value": page_order_key(idx)},
                "template": {"timestamp": "1:1", "value": "P Blank"},
            })

        # 2. Store .pagedata
        pagedata_content = "\n".join(["P Blank"] * len(page_ids)) + "\n"
        pagedata_bytes = pagedata_content.encode("utf-8")
        pagedata_hash = hashlib.sha256(pagedata_bytes).hexdigest()
        self.blob_store.put(pagedata_hash, pagedata_bytes)
        files_meta.append({
            "file_id": f"{doc_id}.pagedata",
            "blob_hash": pagedata_hash,
            "file_type": "pagedata",
            "size": len(pagedata_bytes),
        })

        # 3. Store .content
        content_dict = {
            "cPages": {
                "lastOpened": {"timestamp": "1:1", "value": page_ids[0]},
                "original": {"timestamp": "0:0", "value": -1},
                "pages": c_pages_list,
            },
            "crdt": True,
            "dummyDocument": False,
            "extraMetadata": {},
            "fileType": "epub",
            "formatVersion": 2,
            "lineHeight": -1,
            "margins": 125,
            "orientation": "portrait",
            "originalPageCount": page_count,
            "pageCount": page_count,
            "pages": page_ids,
            "pageTags": [],
            "sizeInBytes": str(len(epub_bytes)),
            "textAlignment": "left",
            "textScale": 1,
        }
        content_bytes = json.dumps(content_dict, indent=2).encode("utf-8")
        content_hash = hashlib.sha256(content_bytes).hexdigest()
        self.blob_store.put(content_hash, content_bytes)
        files_meta.append({
            "file_id": f"{doc_id}.content",
            "blob_hash": content_hash,
            "file_type": "content",
            "size": len(content_bytes),
        })

        # 4. Store .metadata
        meta_dict = {
            "createdTime": now_ms,
            "lastModified": now_ms,
            "lastOpened": now_ms,
            "lastOpenedPage": 0,
            "new": True,
            "parent": parent_id or "",
            "pinned": False,
            "source": "",
            "type": "DocumentType",
            "visibleName": title,
        }
        meta_bytes = json.dumps(meta_dict, indent=2).encode("utf-8")
        meta_hash = hashlib.sha256(meta_bytes).hexdigest()
        self.blob_store.put(meta_hash, meta_bytes)
        files_meta.append({
            "file_id": f"{doc_id}.metadata",
            "blob_hash": meta_hash,
            "file_type": "metadata",
            "size": len(meta_bytes),
        })

        entries = [
            Entry(
                hash=f["blob_hash"],
                type="0",
                doc_id=f["file_id"],
                subfiles=0,
                size=f["size"],
            )
            for f in files_meta
        ]
        doc_hash = compute_doc_index_hash(entries)

        doc_record = {
            "id": doc_id,
            "visible_name": title,
            "type": "DocumentType",
            "parent_id": parent_id or "",
            "last_modified": now_ms,
            "last_opened": now_ms,
            "last_opened_page": 0,
            "pinned": False,
            "deleted": False,
            "file_type": "epub",
            "page_count": page_count,
            "doc_hash": doc_hash,
        }
        self.db.upsert_document(doc_record)
        self.db.set_document_files(doc_hash, files_meta)
        self.db.set_document_pages(doc_hash, doc_pages_meta)

        logger.info("Imported EPUB document %s (%s) with %d pages", title, doc_id, page_count)
        return {
            "id": doc_id,
            "visible_name": title,
            "page_count": page_count,
            "doc_hash": doc_hash,
            "parent_id": parent_id or "",
            "file_type": "epub",
        }

    def create_folder(self, name: str, parent_id: str = "") -> dict[str, Any]:
        """Create a new folder (CollectionType) in the library or nested inside a parent folder."""
        folder_name = name.strip()
        if not folder_name:
            raise ValueError("Folder name cannot be empty")

        if parent_id:
            parent = self.db.get_document(parent_id)
            if not parent:
                raise FileNotFoundError(f"Parent folder {parent_id} not found")
            if parent.get("type") != "CollectionType":
                raise ValueError(f"Parent {parent_id} is not a folder")

        folder_id = str(uuid.uuid4())
        now_ms = str(int(time.time() * 1000))

        meta_dict = {
            "createdTime": now_ms,
            "lastModified": now_ms,
            "new": True,
            "parent": parent_id or "",
            "pinned": False,
            "source": "",
            "type": "CollectionType",
            "visibleName": folder_name,
        }
        meta_bytes = json.dumps(meta_dict, indent=2).encode("utf-8")
        meta_hash = hashlib.sha256(meta_bytes).hexdigest()
        self.blob_store.put(meta_hash, meta_bytes)

        entries = [
            Entry(
                hash=meta_hash,
                type="0",
                doc_id=f"{folder_id}.metadata",
                subfiles=0,
                size=len(meta_bytes),
            )
        ]
        doc_hash = compute_doc_index_hash(entries)

        doc_record = {
            "id": folder_id,
            "visible_name": folder_name,
            "type": "CollectionType",
            "parent_id": parent_id or "",
            "last_modified": now_ms,
            "last_opened": "",
            "last_opened_page": 0,
            "pinned": False,
            "deleted": False,
            "file_type": "",
            "page_count": 0,
            "doc_hash": doc_hash,
        }
        self.db.upsert_document(doc_record)
        self.db.set_document_files(doc_hash, [{
            "file_id": f"{folder_id}.metadata",
            "blob_hash": meta_hash,
            "file_type": "metadata",
            "size": len(meta_bytes),
        }])

        return doc_record

    def move_document(self, doc_id: str, new_parent_id: str = "") -> dict[str, Any]:
        """Move a document or folder to a new parent folder (or root "")."""
        doc = self.db.get_document(doc_id)
        if not doc:
            raise FileNotFoundError(f"Document {doc_id} not found")

        # The Tasks notebook must always stay on the main page (root)
        if (
            doc.get("type") != "CollectionType"
            and doc.get("visible_name", "").strip().lower() == "tasks"
            and new_parent_id != ""
        ):
            raise ValueError("The Tasks notebook must remain on the main page.")

        is_collection = doc.get("type") == "CollectionType"
        if is_collection:
            if new_parent_id == doc_id:
                raise ValueError("Cannot move a folder into itself")
            descendants = self.db.get_descendant_ids(doc_id)
            if new_parent_id in descendants:
                raise ValueError("Cannot move a folder into its own subfolder")

        if new_parent_id:
            parent = self.db.get_document(new_parent_id)
            if not parent:
                raise FileNotFoundError(f"Target folder {new_parent_id} not found")
            if parent.get("type") != "CollectionType":
                raise ValueError(f"Target {new_parent_id} is not a folder")

        # Update metadata blob if present
        now_ms = str(int(time.time() * 1000))
        meta_key = f"{doc_id}.metadata"
        files = doc.get("files", [])
        meta_file = next((f for f in files if f["file_id"] == meta_key), None)
        if meta_file and self.blob_store.has(meta_file["blob_hash"]):
            try:
                meta_dict = json.loads(self.blob_store.get(meta_file["blob_hash"]).decode("utf-8"))
            except Exception:
                meta_dict = {}
            meta_dict["parent"] = new_parent_id or ""
            meta_dict["lastModified"] = now_ms
            new_meta_bytes = json.dumps(meta_dict, indent=2).encode("utf-8")
            new_meta_hash = hashlib.sha256(new_meta_bytes).hexdigest()
            self.blob_store.put(new_meta_hash, new_meta_bytes)

            updated_files = [
                {**f, "blob_hash": new_meta_hash, "size": len(new_meta_bytes)}
                if f["file_id"] == meta_key else f
                for f in files
            ]
            entries = [
                Entry(hash=f["blob_hash"], type="0", doc_id=f["file_id"], subfiles=0, size=f["size"])
                for f in updated_files
            ]
            new_doc_hash = compute_doc_index_hash(entries)
            self.db.set_document_files(new_doc_hash, updated_files)
            doc["doc_hash"] = new_doc_hash

        # Update DB parent_id
        self.db.update_document_parent(doc_id, new_parent_id)
        doc["parent_id"] = new_parent_id
        doc["last_modified"] = now_ms
        self.db.upsert_document(doc)

        return {
            "id": doc_id,
            "visible_name": doc["visible_name"],
            "parent_id": new_parent_id,
            "type": doc["type"],
        }

    def delete_document(self, doc_id: str) -> dict[str, Any]:
        """Soft delete a document or folder (including all nested descendants)."""
        doc = self.db.get_document(doc_id)
        if not doc:
            raise FileNotFoundError(f"Document {doc_id} not found")

        affected_ids = self.db.soft_delete_document(doc_id)

        # Update metadata blob as deleted
        now_ms = str(int(time.time() * 1000))
        meta_key = f"{doc_id}.metadata"
        files = doc.get("files", [])
        meta_file = next((f for f in files if f["file_id"] == meta_key), None)
        if meta_file and self.blob_store.has(meta_file["blob_hash"]):
            try:
                meta_dict = json.loads(self.blob_store.get(meta_file["blob_hash"]).decode("utf-8"))
            except Exception:
                meta_dict = {}
            meta_dict["deleted"] = True
            meta_dict["lastModified"] = now_ms
            new_meta_bytes = json.dumps(meta_dict, indent=2).encode("utf-8")
            new_meta_hash = hashlib.sha256(new_meta_bytes).hexdigest()
            self.blob_store.put(new_meta_hash, new_meta_bytes)

        return {
            "id": doc_id,
            "visible_name": doc["visible_name"],
            "deleted_ids": affected_ids,
        }
