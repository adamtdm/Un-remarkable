"""SQLite database for reMarkable documents, snapshots, versions, and full-text search."""

from __future__ import annotations

import contextlib
import logging
import sqlite3
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from rmcompanion.config import Settings, get_settings

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sync_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshots (
    root_hash TEXT PRIMARY KEY,
    generation INTEGER NOT NULL,
    schema_version TEXT NOT NULL,
    doc_count INTEGER NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshot_docs (
    root_hash TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    doc_hash TEXT NOT NULL,
    PRIMARY KEY (root_hash, doc_id)
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    visible_name TEXT NOT NULL,
    type TEXT NOT NULL,             -- DocumentType or CollectionType
    parent_id TEXT NOT NULL DEFAULT '',
    last_modified TEXT NOT NULL DEFAULT '',
    last_opened TEXT NOT NULL DEFAULT '',
    last_opened_page INTEGER NOT NULL DEFAULT 0,
    pinned BOOLEAN NOT NULL DEFAULT 0,
    deleted BOOLEAN NOT NULL DEFAULT 0,
    exclude_from_search BOOLEAN NOT NULL DEFAULT 0,
    file_type TEXT NOT NULL DEFAULT 'notebook', -- notebook, pdf, epub
    page_count INTEGER NOT NULL DEFAULT 0,
    doc_hash TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS document_versions (
    doc_id TEXT NOT NULL,
    doc_hash TEXT NOT NULL,
    visible_name TEXT NOT NULL,
    last_modified TEXT NOT NULL,
    seen_at REAL NOT NULL,
    PRIMARY KEY (doc_id, doc_hash)
);

CREATE TABLE IF NOT EXISTS document_files (
    doc_hash TEXT NOT NULL,
    file_id TEXT NOT NULL,
    blob_hash TEXT NOT NULL,
    file_type TEXT NOT NULL DEFAULT '',
    size INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (doc_hash, file_id)
);

CREATE TABLE IF NOT EXISTS document_pages (
    doc_hash TEXT NOT NULL,
    page_idx INTEGER NOT NULL,
    page_id TEXT NOT NULL,
    deleted BOOLEAN NOT NULL DEFAULT 0,
    redir INTEGER NOT NULL DEFAULT -1,
    PRIMARY KEY (doc_hash, page_idx)
);

CREATE TABLE IF NOT EXISTS document_tags (
    doc_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    page_id TEXT NOT NULL DEFAULT '',
    timestamp INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (doc_id, tag, page_id)
);

-- Full-text search virtual table
CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
    doc_id,
    page_idx,
    source,      -- 'title', 'tag', 'typed_text', 'highlight', 'pdf_text'
    content,
    tokenize = 'porter unicode61'
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL,
    page_idx INTEGER NOT NULL DEFAULT 0,
    raw_text TEXT NOT NULL,
    clean_text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',         -- 'open', 'completed'
    marker_type TEXT NOT NULL DEFAULT 'star',     -- 'star', 'checkbox', 'todo'
    fingerprint TEXT UNIQUE,
    created_at REAL NOT NULL,
    completed_at REAL
);

CREATE INDEX IF NOT EXISTS idx_docs_parent ON documents(parent_id, deleted);
CREATE INDEX IF NOT EXISTS idx_docs_type ON documents(type, deleted);
CREATE INDEX IF NOT EXISTS idx_doc_files ON document_files(doc_hash);
CREATE INDEX IF NOT EXISTS idx_doc_pages ON document_pages(doc_hash, page_idx);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_doc ON tasks(doc_id, page_idx);
"""


class Database:
    """Manages SQLite connection, schema initialization, and transactional queries."""

    def __init__(self, db_path: Path | str | None = None, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.db_path = Path(db_path) if db_path else self.settings.db_path
        self._init_db()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)
            # Automatic schema migration for existing databases
            try:
                conn.execute("ALTER TABLE documents ADD COLUMN exclude_from_search BOOLEAN NOT NULL DEFAULT 0")
            except sqlite3.OperationalError:
                pass  # column already exists

    @contextlib.contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=30.0,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # --- Sync State ---

    def get_state(self, key: str, default: str = "") -> str:
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM sync_state WHERE key = ?", (key,)).fetchone()
            return str(row["value"]) if row else default

    def set_state(self, key: str, value: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sync_state (key, value, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (key, str(value), time.time()),
            )

    # --- Snapshots ---

    def record_snapshot(
        self,
        root_hash: str,
        generation: int,
        schema_version: str,
        doc_entries: list[tuple[str, str]],  # (doc_id, doc_hash)
    ) -> None:
        now = time.time()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO snapshots (root_hash, generation, schema_version, doc_count, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (root_hash, generation, schema_version, len(doc_entries), now),
            )
            conn.executemany(
                """
                INSERT OR REPLACE INTO snapshot_docs (root_hash, doc_id, doc_hash)
                VALUES (?, ?, ?)
                """,
                [(root_hash, doc_id, doc_hash) for doc_id, doc_hash in doc_entries],
            )

    def list_snapshots(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as conn:
            cur = conn.execute(
                "SELECT root_hash, generation, schema_version, doc_count, created_at FROM snapshots ORDER BY generation DESC LIMIT ?",
                (limit,),
            )
            return [dict(r) for r in cur.fetchall()]

    # --- Documents ---

    def upsert_document(self, doc_data: dict[str, Any]) -> None:
        now = time.time()
        doc_id = doc_data["id"]
        doc_hash = doc_data.get("doc_hash", "")
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO documents (
                    id, visible_name, type, parent_id, last_modified, last_opened,
                    last_opened_page, pinned, deleted, file_type, page_count, doc_hash,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    visible_name = excluded.visible_name,
                    type = excluded.type,
                    parent_id = excluded.parent_id,
                    last_modified = excluded.last_modified,
                    last_opened = excluded.last_opened,
                    last_opened_page = excluded.last_opened_page,
                    pinned = excluded.pinned,
                    deleted = excluded.deleted,
                    file_type = excluded.file_type,
                    page_count = excluded.page_count,
                    doc_hash = excluded.doc_hash,
                    updated_at = excluded.updated_at
                """,
                (
                    doc_id,
                    doc_data.get("visible_name", ""),
                    doc_data.get("type", "DocumentType"),
                    doc_data.get("parent_id", ""),
                    doc_data.get("last_modified", ""),
                    doc_data.get("last_opened", ""),
                    int(doc_data.get("last_opened_page", 0)),
                    bool(doc_data.get("pinned", False)),
                    bool(doc_data.get("deleted", False)),
                    doc_data.get("file_type", "notebook"),
                    int(doc_data.get("page_count", 0)),
                    doc_hash,
                    now,
                    now,
                ),
            )

            # Record version history
            if doc_hash:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO document_versions (doc_id, doc_hash, visible_name, last_modified, seen_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (doc_id, doc_hash, doc_data.get("visible_name", ""), doc_data.get("last_modified", ""), now),
                )

            # Update title in search index
            conn.execute("DELETE FROM search_index WHERE doc_id = ? AND source = 'title'", (doc_id,))
            if not doc_data.get("deleted", False) and doc_data.get("parent_id") != "trash":
                conn.execute(
                    "INSERT INTO search_index (doc_id, page_idx, source, content) VALUES (?, 0, 'title', ?)",
                    (doc_id, doc_data.get("visible_name", "")),
                )

    def set_document_files(self, doc_hash: str, files: list[dict[str, Any]]) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM document_files WHERE doc_hash = ?", (doc_hash,))
            conn.executemany(
                """
                INSERT INTO document_files (doc_hash, file_id, blob_hash, file_type, size)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (doc_hash, f["file_id"], f["blob_hash"], f.get("file_type", ""), int(f.get("size", 0)))
                    for f in files
                ],
            )

    def get_document_files(self, doc_id_or_hash: str) -> list[dict[str, Any]]:
        """Get document files for a document ID or doc_hash."""
        with self.connect() as conn:
            cur = conn.execute(
                """
                SELECT DISTINCT df.file_id, df.blob_hash, df.file_type, df.size 
                FROM document_files df
                LEFT JOIN documents d ON d.doc_hash = df.doc_hash
                WHERE (d.id = ? AND d.doc_hash != '') OR df.doc_hash = ?
                """,
                (doc_id_or_hash, doc_id_or_hash),
            )
            return [dict(r) for r in cur.fetchall()]

    def set_document_pages(self, doc_hash: str, pages: list[dict[str, Any]]) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM document_pages WHERE doc_hash = ?", (doc_hash,))
            conn.executemany(
                """
                INSERT INTO document_pages (doc_hash, page_idx, page_id, deleted, redir)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (doc_hash, p["page_idx"], p["page_id"], bool(p.get("deleted", False)), int(p.get("redir", -1)))
                    for p in pages
                ],
            )

    def set_document_tags(self, doc_id: str, tags: list[dict[str, Any]]) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM document_tags WHERE doc_id = ?", (doc_id,))
            conn.executemany(
                """
                INSERT OR IGNORE INTO document_tags (doc_id, tag, page_id, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                [(doc_id, t["tag"], t.get("page_id", ""), int(t.get("timestamp", 0))) for t in tags],
            )
            # Update tag search index
            conn.execute("DELETE FROM search_index WHERE doc_id = ? AND source = 'tag'", (doc_id,))
            unique_tags = {t["tag"] for t in tags}
            if unique_tags:
                conn.execute(
                    "INSERT INTO search_index (doc_id, page_idx, source, content) VALUES (?, 0, 'tag', ?)",
                    (doc_id, " ".join(unique_tags)),
                )

    def get_document(self, doc_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
            if not row:
                return None
            doc = dict(row)
            doc["pinned"] = bool(doc.get("pinned", False))
            doc["deleted"] = bool(doc.get("deleted", False))
            # Fetch tags
            tags_cur = conn.execute(
                "SELECT tag, page_id, timestamp FROM document_tags WHERE doc_id = ?", (doc_id,)
            )
            doc["tags"] = [dict(t) for t in tags_cur.fetchall()]

            # Fetch pages if doc_hash is present
            if doc["doc_hash"]:
                pages_cur = conn.execute(
                    "SELECT page_idx, page_id, deleted, redir FROM document_pages WHERE doc_hash = ? ORDER BY page_idx ASC",
                    (doc["doc_hash"],),
                )
                doc["pages"] = [dict(p) for p in pages_cur.fetchall()]

                files_cur = conn.execute(
                    "SELECT file_id, blob_hash, file_type, size FROM document_files WHERE doc_hash = ?",
                    (doc["doc_hash"],),
                )
                doc["files"] = [dict(f) for f in files_cur.fetchall()]
            else:
                doc["pages"] = []
                doc["files"] = []
            doc["exclude_from_search"] = bool(doc.get("exclude_from_search", False))
            doc["effective_exclude"] = self.is_excluded_from_search(doc_id)
            return doc

    def list_documents(
        self,
        parent_id: str | None = None,
        include_deleted: bool = False,
        file_type: str | None = None,
    ) -> list[dict[str, Any]]:
        query = """
        SELECT d.*, COALESCE(df.total_size, 0) AS total_size
        FROM documents d
        LEFT JOIN (
            SELECT doc_hash, SUM(size) AS total_size
            FROM document_files
            WHERE doc_hash != ''
            GROUP BY doc_hash
        ) df ON d.doc_hash = df.doc_hash AND d.doc_hash != ''
        WHERE 1=1
        """
        params: list[Any] = []

        if not include_deleted:
            query += " AND d.deleted = 0"

        if parent_id is not None:
            query += " AND d.parent_id = ?"
            params.append(parent_id)

        if file_type is not None and file_type != "":
            if file_type.lower() in ("folder", "collection", "collectiontype"):
                query += " AND d.type = 'CollectionType'"
            else:
                query += " AND d.file_type = ? AND d.type = 'DocumentType'"
                params.append(file_type)

        query += " ORDER BY d.type DESC, d.visible_name ASC"

        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            excluded_ids = self.get_all_excluded_ids()
            results = []
            for r in rows:
                d = dict(r)
                d["pinned"] = bool(d.get("pinned", False))
                d["deleted"] = bool(d.get("deleted", False))
                d["exclude_from_search"] = bool(d.get("exclude_from_search", False))
                d["effective_exclude"] = bool(d["id"] in excluded_ids or d["exclude_from_search"])
                size = int(d.get("total_size") or 0)
                d["total_size"] = size
                d["needs_optimization"] = (
                    d.get("type") != "CollectionType"
                    and (
                        size > 30 * 1024 * 1024
                        or (d.get("file_type") == "epub" and size > 15 * 1024 * 1024)
                        or (d.get("page_count", 0) > 150)
                    )
                )
                results.append(d)
            return results

    def is_excluded_from_search(self, doc_id: str) -> bool:
        """Check if document or any of its parent folders are marked exclude_from_search."""
        current_id = doc_id
        visited: set[str] = set()
        with self.connect() as conn:
            while current_id and current_id not in visited:
                visited.add(current_id)
                row = conn.execute(
                    "SELECT parent_id, exclude_from_search FROM documents WHERE id = ?",
                    (current_id,),
                ).fetchone()
                if not row:
                    break
                if row["exclude_from_search"]:
                    return True
                current_id = row["parent_id"]
        return False

    def get_all_excluded_ids(self) -> set[str]:
        """Return a set of all document and folder IDs that are excluded (explicitly or via parent)."""
        with self.connect() as conn:
            cur = conn.execute("SELECT id, parent_id, exclude_from_search FROM documents WHERE deleted = 0")
            rows = cur.fetchall()

        parents: dict[str, str] = {}
        explicitly_excluded: set[str] = set()
        for r in rows:
            doc_id = r["id"]
            parents[doc_id] = r["parent_id"] or ""
            if r["exclude_from_search"]:
                explicitly_excluded.add(doc_id)

        if not explicitly_excluded:
            return set()

        all_excluded: set[str] = set(explicitly_excluded)
        for doc_id in parents:
            curr = doc_id
            visited: set[str] = set()
            while curr and curr not in visited:
                visited.add(curr)
                if curr in explicitly_excluded:
                    all_excluded.add(doc_id)
                    break
                curr = parents.get(curr, "")
        return all_excluded

    def get_descendant_ids(self, folder_id: str) -> list[str]:
        """Get all descendant document and collection IDs under folder_id."""
        descendants: list[str] = []
        queue = [folder_id]
        with self.connect() as conn:
            while queue:
                curr = queue.pop(0)
                rows = conn.execute(
                    "SELECT id, type FROM documents WHERE parent_id = ? AND deleted = 0",
                    (curr,),
                ).fetchall()
                for r in rows:
                    descendants.append(r["id"])
                    if r["type"] == "CollectionType":
                        queue.append(r["id"])
        return descendants

    def get_folder_tree(self) -> list[dict[str, Any]]:
        """Get all non-deleted folders with hierarchical path, depth, and child counts."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT id, visible_name, parent_id, last_modified, exclude_from_search FROM documents WHERE type = 'CollectionType' AND deleted = 0"
            ).fetchall()

        folder_map = {r["id"]: dict(r) for r in rows}
        excluded_ids = self.get_all_excluded_ids()

        def get_path_info(fid: str) -> tuple[str, int]:
            curr = folder_map.get(fid)
            if not curr:
                return ("", 0)
            parts = [curr["visible_name"]]
            depth = 0
            visited = {fid}
            p = curr.get("parent_id", "")
            while p and p in folder_map and p not in visited:
                visited.add(p)
                p_item = folder_map[p]
                parts.insert(0, p_item["visible_name"])
                depth += 1
                p = p_item.get("parent_id", "")
            return (" / ".join(parts), depth)

        result = []
        for fid, f in folder_map.items():
            path_str, depth = get_path_info(fid)
            is_exc = bool(f.get("exclude_from_search", False))
            result.append({
                "id": f["id"],
                "visible_name": f["visible_name"],
                "parent_id": f.get("parent_id", ""),
                "path": path_str,
                "depth": depth,
                "exclude_from_search": is_exc,
                "effective_exclude": bool(fid in excluded_ids or is_exc),
            })

        result.sort(key=lambda x: x["path"].lower())
        return result

    def update_document_parent(self, doc_id: str, new_parent_id: str = "") -> None:
        """Update parent_id of a document or collection."""
        now = time.time()
        with self.connect() as conn:
            conn.execute(
                "UPDATE documents SET parent_id = ?, updated_at = ? WHERE id = ?",
                (new_parent_id, now, doc_id),
            )

    def soft_delete_document(self, doc_id: str) -> list[str]:
        """Mark document and all its descendants as deleted. Purges search index and tasks."""
        row = self.get_document(doc_id)
        if not row:
            return []

        affected_ids = [doc_id]
        if row.get("type") == "CollectionType":
            descendants = self.get_descendant_ids(doc_id)
            affected_ids.extend(descendants)

        now = time.time()
        placeholders = ",".join("?" for _ in affected_ids)
        with self.connect() as conn:
            conn.execute(
                f"UPDATE documents SET deleted = 1, updated_at = ? WHERE id IN ({placeholders})",
                [now, *affected_ids],
            )
            conn.execute(
                f"DELETE FROM search_index WHERE doc_id IN ({placeholders})",
                affected_ids,
            )
            conn.execute(
                f"DELETE FROM tasks WHERE doc_id IN ({placeholders})",
                affected_ids,
            )
        return affected_ids

    def set_exclude_from_search(self, doc_id: str, exclude: bool) -> list[str]:
        """Toggle exclusion for a document or folder. Recursively excludes all descendants. Purges non-title search index entries if excluded."""
        with self.connect() as conn:
            affected_ids = [doc_id]
            row = conn.execute("SELECT type FROM documents WHERE id = ?", (doc_id,)).fetchone()
            if row and row["type"] == "CollectionType":
                descendants = self.get_descendant_ids(doc_id)
                affected_ids.extend(descendants)

            placeholders = ",".join("?" for _ in affected_ids)
            conn.execute(
                f"UPDATE documents SET exclude_from_search = ? WHERE id IN ({placeholders})",
                [1 if exclude else 0, *affected_ids],
            )

            if exclude:
                conn.execute(
                    f"DELETE FROM search_index WHERE doc_id IN ({placeholders}) AND source NOT IN ('title')",
                    affected_ids,
                )
                conn.execute(
                    f"DELETE FROM tasks WHERE doc_id IN ({placeholders})",
                    affected_ids,
                )
            return affected_ids

    def list_versions(self, doc_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            cur = conn.execute(
                """
                SELECT doc_id, doc_hash, visible_name, last_modified, seen_at
                FROM document_versions
                WHERE doc_id = ?
                ORDER BY seen_at DESC
                """,
                (doc_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    # --- Search ---

    def index_content(self, doc_id: str, page_idx: int, source: str, content: str) -> None:
        """Add content to FTS5 search index."""
        if not content.strip():
            return
        with self.connect() as conn:
            conn.execute(
                "DELETE FROM search_index WHERE doc_id = ? AND page_idx = ? AND source = ?",
                (doc_id, page_idx, source),
            )
            conn.execute(
                "INSERT INTO search_index (doc_id, page_idx, source, content) VALUES (?, ?, ?, ?)",
                (doc_id, page_idx, source, content),
            )

    def search(
        self,
        query: str,
        limit: int = 25,
        only_notes: bool = False,
        include_excluded: bool = False,
    ) -> list[dict[str, Any]]:
        clean_query = query.strip()
        if not clean_query:
            return []
        # Support simple token matching in FTS5
        words = [w.replace('"', '""') for w in clean_query.split() if w]
        fts_query = " ".join(f'"{w}"*' for w in words)

        note_filter = "AND d.file_type = 'notebook'" if only_notes else ""
        exclude_filter = "" if include_excluded else "AND d.exclude_from_search = 0 AND d.parent_id != 'trash'"

        sql = f"""
        SELECT
            s.doc_id,
            s.page_idx,
            s.source,
            snippet(search_index, 3, '<mark>', '</mark>', '...', 20) AS snippet,
            d.visible_name,
            d.type,
            d.file_type,
            d.parent_id,
            d.exclude_from_search
        FROM search_index s
        JOIN documents d ON s.doc_id = d.id
        WHERE search_index MATCH ? AND d.deleted = 0 {note_filter} {exclude_filter}
        ORDER BY rank
        LIMIT ?
        """
        fetch_limit = limit * 2 if not include_excluded else limit
        with self.connect() as conn:
            try:
                cur = conn.execute(sql, (fts_query, fetch_limit))
                results = [dict(r) for r in cur.fetchall()]
            except sqlite3.OperationalError:
                # Fallback for complex syntax
                cur = conn.execute(
                    f"""
                    SELECT
                        s.doc_id,
                        s.page_idx,
                        s.source,
                        substr(s.content, 1, 120) AS snippet,
                        d.visible_name,
                        d.type,
                        d.file_type,
                        d.parent_id,
                        d.exclude_from_search
                    FROM search_index s
                    JOIN documents d ON s.doc_id = d.id
                    WHERE s.content LIKE ? AND d.deleted = 0 {note_filter} {exclude_filter}
                    LIMIT ?
                    """,
                    (f"%{clean_query}%", fetch_limit),
                )
                results = [dict(r) for r in cur.fetchall()]

            if not include_excluded:
                excluded_ids = self.get_all_excluded_ids()
                results = [
                    r for r in results
                    if r["doc_id"] not in excluded_ids
                    and not r.get("exclude_from_search")
                    and r.get("parent_id") != "trash"
                ]
            return results[:limit]

    # --- Task Consolidation ---

    def upsert_task(self, task_data: dict[str, Any]) -> None:
        """Insert or update a task, respecting fingerprint deduplication."""
        now = time.time()
        fingerprint = task_data.get("fingerprint") or ""
        with self.connect() as conn:
            if fingerprint:
                existing = conn.execute("SELECT id, status FROM tasks WHERE fingerprint = ?", (fingerprint,)).fetchone()
                if existing:
                    return

            conn.execute(
                """
                INSERT INTO tasks (id, doc_id, page_idx, raw_text, clean_text, status, marker_type, fingerprint, created_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(fingerprint) DO UPDATE SET
                    raw_text = excluded.raw_text,
                    clean_text = excluded.clean_text
                """,
                (
                    task_data["id"],
                    task_data["doc_id"],
                    task_data.get("page_idx", 0),
                    task_data["raw_text"],
                    task_data["clean_text"],
                    task_data.get("status", "open"),
                    task_data.get("marker_type", "star"),
                    fingerprint,
                    task_data.get("created_at", now),
                    task_data.get("completed_at"),
                ),
            )

    def list_tasks(self, status: str | None = None, doc_id: str | None = None) -> list[dict[str, Any]]:
        query = """
        SELECT t.*, d.visible_name AS doc_name, d.parent_id, d.exclude_from_search AS doc_excluded, d.deleted AS doc_deleted
        FROM tasks t
        LEFT JOIN documents d ON t.doc_id = d.id
        WHERE (d.deleted IS NULL OR d.deleted = 0)
        """
        params: list[Any] = []
        if status:
            query += " AND t.status = ?"
            params.append(status)
        if doc_id:
            query += " AND t.doc_id = ?"
            params.append(doc_id)
        query += " ORDER BY t.status ASC, t.created_at DESC"

        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            if not rows:
                return []
            excluded_ids = self.get_all_excluded_ids()
            return [
                dict(r) for r in rows
                if not (r["doc_id"] and r["doc_id"] in excluded_ids)
            ]

    def set_task_status(self, task_id: str, status: str) -> bool:
        now = time.time() if status == "completed" else None
        with self.connect() as conn:
            cur = conn.execute(
                "UPDATE tasks SET status = ?, completed_at = ? WHERE id = ?",
                (status, now, task_id),
            )
            return cur.rowcount > 0

    def delete_task(self, task_id: str) -> bool:
        with self.connect() as conn:
            cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            return cur.rowcount > 0

    def count_open_tasks(self) -> int:
        return len(self.list_tasks(status="open"))
