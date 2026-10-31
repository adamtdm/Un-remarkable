"""Parsing, serializing, and canonical hashing of sync15 schema v3 & v4 indexes."""

from __future__ import annotations

import binascii
import hashlib
from dataclasses import dataclass

SCHEMA_V3 = "3"
SCHEMA_V4 = "4"

DOC_TYPE = "80000000"
FILE_TYPE = "0"
DELIMITER = ":"


@dataclass
class Entry:
    hash: str
    type: str
    doc_id: str
    subfiles: int
    size: int

    def to_line(self) -> str:
        # Canonical rmapi entry format: hash:type:doc_id:subfiles:size
        return f"{self.hash}{DELIMITER}{self.type}{DELIMITER}{self.doc_id}{DELIMITER}{self.subfiles}{DELIMITER}{self.size}"

    @property
    def is_document(self) -> bool:
        return self.type == DOC_TYPE or self.subfiles > 0

    @property
    def is_file(self) -> bool:
        return self.type == FILE_TYPE and self.subfiles == 0


def parse_entry_line(line: str) -> Entry:
    parts = line.strip().split(DELIMITER)
    if len(parts) != 5:
        raise ValueError(f"Invalid entry line (expected 5 fields, got {len(parts)}): {line!r}")
    return Entry(
        hash=parts[0],
        type=parts[1],
        doc_id=parts[2],
        subfiles=int(parts[3]),
        size=int(parts[4]),
    )


def parse_index(content: str | bytes) -> tuple[list[Entry], str]:
    """Parse a sync15 index file (schema 3 or 4).

    Returns:
        (entries, schema_version)
    """
    if isinstance(content, bytes):
        text = content.decode("utf-8")
    else:
        text = content

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("Empty index content")

    schema = lines[0]
    entries: list[Entry] = []

    if schema == SCHEMA_V4:
        if len(lines) < 2:
            raise ValueError("Schema v4 index missing summary header line")
        # Line 1 is summary: 0:.:<count>:<size>
        entry_lines = lines[2:]
        for line in entry_lines:
            entries.append(parse_entry_line(line))
    elif schema == SCHEMA_V3:
        entry_lines = lines[1:]
        for line in entry_lines:
            entries.append(parse_entry_line(line))
    else:
        raise ValueError(f"Unsupported index schema version: {schema}")

    return entries, schema


def format_index(entries: list[Entry], schema: str = SCHEMA_V4) -> str:
    """Format entries into canonical index string sorted by doc_id."""
    sorted_entries = sorted(entries, key=lambda e: e.doc_id)
    out: list[str] = [schema]

    if schema == SCHEMA_V4:
        total_size = sum(e.size for e in sorted_entries)
        out.append(f"0{DELIMITER}.{DELIMITER}{len(sorted_entries)}{DELIMITER}{total_size}")

    for e in sorted_entries:
        out.append(e.to_line())

    out.append("")  # trailing newline
    return "\n".join(out)


def compute_doc_index_hash(entries: list[Entry]) -> str:
    """Compute document-level index hash (schema 3 HashEntries).

    Sorted by doc_id ascending, then SHA-256 of concatenated raw binary hashes.
    """
    sorted_entries = sorted(entries, key=lambda e: e.doc_id)
    hasher = hashlib.sha256()
    for e in sorted_entries:
        try:
            raw_hash = binascii.unhexlify(e.hash)
        except binascii.Error as exc:
            raise ValueError(f"Invalid hex hash {e.hash!r} in entry: {exc}") from exc
        hasher.update(raw_hash)
    return hasher.hexdigest()


def compute_root_hash(index_content: str | bytes) -> str:
    """Compute root index hash (SHA-256 of serialized text body)."""
    if isinstance(index_content, str):
        data = index_content.encode("utf-8")
    else:
        data = index_content
    return hashlib.sha256(data).hexdigest()
