"""Task extractor parsing to-dos from typed text, notebooks, and vision OCR."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid
from typing import Any

from rmcompanion.intelligence.provider import VisionProvider
from rmcompanion.render.exporter import Exporter
from rmcompanion.store.blob_store import BlobStore
from rmcompanion.store.db import Database

logger = logging.getLogger(__name__)


def extract_tasks_from_text(text: str) -> list[dict[str, Any]]:
    """Extract tasks from typed text according to spec rules.

    Rules:
    - Task starts at '*', '- [ ]', '[ ]', 'TODO:', or 'TODO'.
    - An asterisk task runs until the next '*', a sentence-ending full stop, or a paragraph break.
    - Checkbox tasks capture the line content.
    - Processing runs sequentially to preserve document flow.
    """
    tasks: list[dict[str, Any]] = []
    lines = text.splitlines()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # 1. Asterisk marker at start of line: * or - *
        star_match = re.match(r"^(?:-\s*)?\*\s*(.+)$", stripped)
        if star_match:
            content = star_match.group(1).strip()
            # If multiple asterisks on the same line, stop at the next one
            if "*" in content:
                content = content.split("*")[0].strip()
            # Stop at the first sentence-ending period
            period_match = re.search(r"(?<!\b[a-zA-Z])\.(?:\s|$)", content)
            if period_match:
                task_text = content[: period_match.start() + 1].strip()
            else:
                task_text = content
            if task_text:
                tasks.append({"text": task_text, "marker": "star", "status": "open"})
            continue

        # 2. Checkbox open: - [ ] or [ ]
        cb_open = re.match(r"^(?:-\s*)?\[\s*\]\s+(.+)$", stripped, re.IGNORECASE)
        if cb_open:
            clean = cb_open.group(1).strip()
            if clean:
                tasks.append({"text": clean, "marker": "checkbox", "status": "open"})
            continue

        # 3. Checkbox completed: - [x] or [x]
        cb_done = re.match(r"^(?:-\s*)?\[[xX]\]\s+(.+)$", stripped)
        if cb_done:
            clean = cb_done.group(1).strip()
            if clean:
                tasks.append({"text": clean, "marker": "checkbox", "status": "completed"})
            continue

        # 4. TODO marker
        todo_match = re.match(r"^(?:TODO\s*:?|FIXME\s*:?)\s*(.+)$", stripped, re.IGNORECASE)
        if todo_match:
            clean = todo_match.group(1).strip()
            if clean:
                tasks.append({"text": clean, "marker": "todo", "status": "open"})
            continue

        # 5. Embedded asterisk in line
        if "*" in stripped:
            parts = stripped.split("*")
            for seg in parts[1:]:
                seg = seg.strip()
                if not seg:
                    continue
                period_match = re.search(r"(?<!\b[a-zA-Z])\.(?:\s|$)", seg)
                if period_match:
                    task_text = seg[: period_match.start() + 1].strip()
                else:
                    task_text = seg
                task_text = re.sub(r"^[-•]\s*", "", task_text).strip()
                if task_text and len(task_text) > 2:
                    if not any(t["text"].lower() == task_text.lower() for t in tasks):
                        tasks.append({"text": task_text, "marker": "star", "status": "open"})

    return tasks


class TaskExtractor:
    """Orchestrates task discovery across typed notebooks and vision OCR."""

    def __init__(
        self,
        db: Database,
        blob_store: BlobStore,
        exporter: Exporter,
        vision_provider: VisionProvider | None = None,
    ) -> None:
        self.db = db
        self.blob_store = blob_store
        self.exporter = exporter
        self.vision_provider = vision_provider

    def extract_from_typed_page(self, doc_id: str, page_idx: int, typed_text: str) -> list[dict[str, Any]]:
        """Extract tasks from typed text and save into database."""
        extracted = extract_tasks_from_text(typed_text)
        saved: list[dict[str, Any]] = []

        for item in extracted:
            raw_text = item["text"]
            clean_text = raw_text.rstrip(".")
            fingerprint = hashlib.sha256(f"{doc_id}:{page_idx}:{clean_text.lower()}".encode()).hexdigest()

            task_record = {
                "id": f"task_{uuid.uuid4().hex[:12]}",
                "doc_id": doc_id,
                "page_idx": page_idx,
                "raw_text": raw_text,
                "clean_text": clean_text,
                "status": item["status"],
                "marker_type": item["marker"],
                "fingerprint": fingerprint,
                "created_at": time.time(),
                "completed_at": time.time() if item["status"] == "completed" else None,
            }

            self.db.upsert_task(task_record)
            saved.append(task_record)

        return saved

    async def extract_from_handwriting_page(
        self,
        doc_id: str,
        page_idx: int,
    ) -> list[dict[str, Any]]:
        """Render page to PNG and query Vision Provider for handwritten tasks."""
        if not self.vision_provider:
            return []

        # Check if excluded
        if self.db.is_excluded_from_search(doc_id):
            logger.debug("Skipping vision task extraction for excluded doc %s", doc_id)
            return []

        # Render page PNG
        png_bytes = self.exporter.render_page_png(doc_id, page_idx=page_idx, dark_mode=False)

        prompt = (
            "Analyze this notebook page and extract all to-do items and tasks marked with:\n"
            "1. An asterisk (*)\n"
            "2. A checkbox ([ ], [x], ☐, or ☑)\n"
            "3. The word 'TODO' or 'TASK'\n"
            "4. Handwritten bullet points indicating action items.\n\n"
            "Rules:\n"
            "- A task starting with * runs until the next *, a sentence-ending period, or a line/paragraph break.\n"
            "- Return strictly valid JSON array without Markdown code blocks:\n"
            '[{"text": "task text", "marker": "star"|"checkbox"|"todo", "status": "open"|"completed"}]\n'
            "If no tasks are present on this page, return []"
        )

        try:
            resp_text = await self.vision_provider.analyze_image(
                png_bytes,
                prompt=prompt,
                system_prompt="You are an expert handwriting OCR reader. Always output raw JSON only.",
            )

            # Strip markdown code fences if model returned them
            clean_json = re.sub(r"^```(?:json)?\s*|\s*```$", "", resp_text.strip(), flags=re.DOTALL)
            parsed = json.loads(clean_json)
            if not isinstance(parsed, list):
                return []

            saved: list[dict[str, Any]] = []
            for item in parsed:
                text = str(item.get("text", "")).strip()
                if not text:
                    continue
                clean = text.rstrip(".")
                fingerprint = hashlib.sha256(f"{doc_id}:{page_idx}:{clean.lower()}".encode()).hexdigest()
                status = "completed" if item.get("status") == "completed" else "open"
                marker = item.get("marker", "star")

                task_record = {
                    "id": f"task_{uuid.uuid4().hex[:12]}",
                    "doc_id": doc_id,
                    "page_idx": page_idx,
                    "raw_text": text,
                    "clean_text": clean,
                    "status": status,
                    "marker_type": marker,
                    "fingerprint": fingerprint,
                    "created_at": time.time(),
                    "completed_at": time.time() if status == "completed" else None,
                }
                self.db.upsert_task(task_record)
                saved.append(task_record)

            return saved

        except Exception as e:
            logger.warning("Vision OCR task extraction failed for %s p%d: %s", doc_id, page_idx, e)
            return []

    async def scan_document_for_tasks(self, doc_id: str) -> list[dict[str, Any]]:
        """Scan all pages of a document for tasks (typed text + vision if available)."""
        doc = self.db.get_document(doc_id)
        if not doc or doc.get("deleted"):
            return []

        all_tasks: list[dict[str, Any]] = []
        pages = doc.get("pages", [])

        # 1. First, check typed text indexed in FTS5
        with self.db.connect() as conn:
            cur = conn.execute(
                "SELECT page_idx, content FROM search_index WHERE doc_id = ? AND source = 'typed_text'",
                (doc_id,),
            )
            for row in cur.fetchall():
                p_idx = row["page_idx"]
                text = row["content"]
                tasks = self.extract_from_typed_page(doc_id, p_idx, text)
                all_tasks.extend(tasks)

        # 2. If vision provider is configured, scan handwriting pages
        if self.vision_provider and not self.db.is_excluded_from_search(doc_id):
            for p in pages:
                if p.get("deleted"):
                    continue
                p_idx = p.get("page_idx", 0)
                try:
                    vision_tasks = await self.extract_from_handwriting_page(doc_id, p_idx)
                    all_tasks.extend(vision_tasks)
                except Exception as e:
                    logger.debug("Page %d vision scan error: %s", p_idx, e)

        return all_tasks
