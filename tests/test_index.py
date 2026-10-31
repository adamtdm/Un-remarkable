"""Tests for sync15 index parsing, serializing, and hashing."""

from rmcompanion.cloud.index import (
    Entry,
    compute_doc_index_hash,
    compute_root_hash,
    format_index,
    parse_index,
)


def test_parse_index_v3():
    content = """3
0f83178c4ebe6a60fae0360b74916ee9e1faa5de1c56ab3481eccdc5cb98754f:0:doc1.content:0:993
17eca6c9a540c993f5f5506bb09b7a40993c02fa8f065b1a6a442e412cf2fd04:0:doc1.metadata:0:320
"""
    entries, schema = parse_index(content)
    assert schema == "3"
    assert len(entries) == 2
    assert entries[0].doc_id == "doc1.content"
    assert entries[0].size == 993
    assert entries[1].doc_id == "doc1.metadata"
    assert entries[1].size == 320


def test_parse_index_v4():
    content = """4
0:.:2:1313
0f83178c4ebe6a60fae0360b74916ee9e1faa5de1c56ab3481eccdc5cb98754f:0:doc1.content:0:993
17eca6c9a540c993f5f5506bb09b7a40993c02fa8f065b1a6a442e412cf2fd04:0:doc1.metadata:0:320
"""
    entries, schema = parse_index(content)
    assert schema == "4"
    assert len(entries) == 2
    assert entries[0].doc_id == "doc1.content"
    assert entries[1].doc_id == "doc1.metadata"


def test_format_and_roundtrip_index():
    entries = [
        Entry(hash="bbbb" * 16, type="0", doc_id="z_file.content", subfiles=0, size=50),
        Entry(hash="aaaa" * 16, type="0", doc_id="a_file.metadata", subfiles=0, size=100),
    ]

    formatted = format_index(entries, schema="4")
    assert formatted.startswith("4\n0:.:2:150\n")
    # Must sort canonically by doc_id ascending
    assert formatted.index("a_file.metadata") < formatted.index("z_file.content")

    parsed, schema = parse_index(formatted)
    assert schema == "4"
    assert len(parsed) == 2
    assert parsed[0].doc_id == "a_file.metadata"
    assert parsed[1].doc_id == "z_file.content"


def test_compute_hashes():
    entries = [
        Entry(hash="00" * 32, type="0", doc_id="b.rm", subfiles=0, size=10),
        Entry(hash="11" * 32, type="0", doc_id="a.rm", subfiles=0, size=20),
    ]
    # Doc index hash is deterministic and canonical regardless of input order
    h1 = compute_doc_index_hash(entries)
    h2 = compute_doc_index_hash(list(reversed(entries)))
    assert h1 == h2
    assert len(h1) == 64

    # Root hash is SHA256 of text body
    text = format_index(entries, schema="4")
    root_hash = compute_root_hash(text)
    assert len(root_hash) == 64
