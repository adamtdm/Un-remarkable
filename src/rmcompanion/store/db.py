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

CREATE INDEX IF NOT EXISTS idx_docs_parent ON documents(parent_id, deleted);
CREATE INDEX IF NOT EXISTS idx_docs_type ON documents(type, deleted);
CREATE INDEX IF NOT EXISTS idx_doc_files ON document_files(doc_hash);
CREATE INDEX IF NOT EXISTS idx_doc_pages ON document_pages(doc_hash, page_idx);
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
            if not doc_data.get("deleted", False):
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
            return doc

    def list_documents(
        self,
        parent_id: str | None = None,
        include_deleted: bool = False,
        file_type: str | None = None,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM documents WHERE 1=1"
        params: list[Any] = []

        if not include_deleted:
            query += " AND deleted = 0"

        if parent_id is not None:
            query += " AND parent_id = ?"
            params.append(parent_id)

        if file_type is not None:
            query += " AND file_type = ?"
            params.append(file_type)

        query += " ORDER BY type DESC, visible_name ASC"

        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

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

    def search(self, query: str, limit: int = 25) -> list[dict[str, Any]]:
        clean_query = query.strip()
        if not clean_query:
            return []
        # Support simple token matching in FTS5
        words = [w.replace('"', '""') for w in clean_query.split() if w]
        fts_query = " ".join(f'"{w}"*' for w in words)

        sql = """
        SELECT
            s.doc_id,
            s.page_idx,
            s.source,
            snippet(search_index, 3, '<mark>', '</mark>', '...', 20) AS snippet,
            d.visible_name,
            d.type,
            d.file_type,
            d.parent_id
        FROM search_index s
        JOIN documents d ON s.doc_id = d.id
        WHERE search_index MATCH ? AND d.deleted = 0
        ORDER BY rank
        LIMIT ?
        """
        with self.connect() as conn:
            try:
                cur = conn.execute(sql, (fts_query, limit))
                return [dict(r) for r in cur.fetchall()]
            except sqlite3.OperationalError:
                # Fallback for complex syntax
                cur = conn.execute(
                    """
                    SELECT
                        s.doc_id,
                        s.page_idx,
                        s.source,
                        substr(s.content, 1, 120) AS snippet,
                        d.visible_name,
                        d.type,
                        d.file_type,
                        d.parent_id
                    FROM search_index s
                    JOIN documents d ON s.doc_id = d.id
                    WHERE s.content LIKE ? AND d.deleted = 0
                    LIMIT ?
                    """,
                    (f"%{clean_query}%", limit),
                )
                return [dict(r) for r in cur.fetchall()]
