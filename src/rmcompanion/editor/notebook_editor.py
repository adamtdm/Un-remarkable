"""Notebook editor for creating and modifying reMarkable notebooks and typed text."""

from __future__ import annotations

import binascii
import hashlib
import io
import json
import logging
import time
import uuid
from typing import Any

import rmscene
from rmscene import CrdtId, CrdtSequence, CrdtSequenceItem, LwwValue, RootTextBlock, scene_items as si
from rmscene.text import TextDocument

from rmcompanion.cloud.index import Entry, compute_doc_index_hash
from rmcompanion.intelligence.task_extractor import TaskExtractor
from rmcompanion.store.blob_store import BlobStore
from rmcompanion.store.db import Database

logger = logging.getLogger(__name__)


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
    ) -> dict[str, Any]:
        """Create a new native reMarkable notebook with one or more pages."""
        now_ms = str(int(time.time() * 1000))
        doc_id = str(uuid.uuid4())

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
                "idx": {"timestamp": f"1:{idx + 1}", "value": f"ba{idx}" if idx > 0 else "ba"},
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
            except Exception:
                pass
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

    def append_task_to_tasks_notebook(
        self,
        task_text: str,
        notebook_title: str = "Tasks",
    ) -> dict[str, Any]:
        """Append a task checkbox item to a dedicated reMarkable notebook."""
        docs = self.db.list_documents(include_deleted=False)
        target_doc = next(
            (d for d in docs if d.get("visible_name") == notebook_title and d.get("type") == "DocumentType"),
            None,
        )

        task_line = f"- [ ] {task_text.strip()}"

        if not target_doc:
            # Create a brand new Tasks notebook
            initial = f"# {notebook_title}\n\n{task_line}\n"
            return self.create_notebook(title=notebook_title, initial_text=initial)

        # Existing notebook: append to page 0
        doc_id = target_doc["id"]
        current_text = self.get_page_typed_text(doc_id, 0)
        if current_text:
            updated_text = current_text.rstrip() + f"\n{task_line}\n"
        else:
            updated_text = f"# {notebook_title}\n\n{task_line}\n"

        self.update_page_typed_text(doc_id, 0, updated_text)
        return {
            "id": doc_id,
            "visible_name": notebook_title,
            "task_line": task_line,
        }

    def sync_tasks_to_notebook(self, notebook_title: str = "Tasks") -> dict[str, Any]:
        """Consolidate all open tasks into the synced Tasks notebook."""
        open_tasks = self.db.list_tasks(status="open")
        lines = [f"# {notebook_title}", "", f"Total open tasks: {len(open_tasks)}", ""]

        for t in open_tasks:
            origin = f" ({t.get('doc_name')})" if t.get("doc_name") else ""
            lines.append(f"- [ ] {t.get('clean_text', '')}{origin}")

        content = "\n".join(lines) + "\n"

        docs = self.db.list_documents(include_deleted=False)
        target_doc = next(
            (d for d in docs if d.get("visible_name") == notebook_title and d.get("type") == "DocumentType"),
            None,
        )

        if not target_doc:
            res = self.create_notebook(title=notebook_title, initial_text=content)
            doc_id = res["id"]
        else:
            doc_id = target_doc["id"]
            self.update_page_typed_text(doc_id, 0, content)

        return {
            "id": doc_id,
            "visible_name": notebook_title,
            "task_count": len(open_tasks),
        }

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
