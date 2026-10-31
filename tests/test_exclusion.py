"""Tests for document and folder search/OCR exclusion."""

from rmcompanion.store.db import Database


def test_document_and_folder_exclusion(tmp_path):
    db_file = tmp_path / "test.db"
    db = Database(db_path=db_file)

    # Create folder and document inside folder
    folder_id = "folder-comics-123"
    doc_id = "doc-the-boys-456"

    db.upsert_document({
        "id": folder_id,
        "visible_name": "Comics",
        "type": "CollectionType",
        "parent_id": "",
    })

    db.upsert_document({
        "id": doc_id,
        "visible_name": "The Boys - Vol 1",
        "type": "DocumentType",
        "file_type": "pdf",
        "parent_id": folder_id,
    })

    # Initial state: neither is excluded
    assert not db.is_excluded_from_search(folder_id)
    assert not db.is_excluded_from_search(doc_id)

    # Index some text
    db.index_content(doc_id, 0, "title", "The Boys - Vol 1")
    db.index_content(doc_id, 1, "pdf_text", "Deep superhero satire and dialogue")

    # Search should find it
    results = db.search("satire")
    assert len(results) == 1
    assert results[0]["doc_id"] == doc_id

    # Exclude the folder
    affected = db.set_exclude_from_search(folder_id, True)
    assert folder_id in affected
    assert doc_id in affected

    # Check inheritance: doc should now be effectively excluded because parent folder is
    assert db.is_excluded_from_search(folder_id)
    assert db.is_excluded_from_search(doc_id)

    # Non-title search content should have been purged upon exclusion
    results_after_exclusion = db.search("satire", include_excluded=False)
    assert len(results_after_exclusion) == 0

    # Title match should still work for discovery
    title_results = db.search("The Boys", include_excluded=False)
    assert len(title_results) >= 1
    assert title_results[0]["source"] == "title"


def test_notes_only_search_filter(tmp_path):
    db_file = tmp_path / "test.db"
    db = Database(db_path=db_file)

    note_id = "note-meeting-1"
    pdf_id = "pdf-book-2"

    db.upsert_document({
        "id": note_id,
        "visible_name": "Meeting Notes",
        "type": "DocumentType",
        "file_type": "notebook",
    })
    db.upsert_document({
        "id": pdf_id,
        "visible_name": "Python Guide",
        "type": "DocumentType",
        "file_type": "pdf",
    })

    db.index_content(note_id, 0, "typed_text", "Architecture roadmap discussion")
    db.index_content(pdf_id, 0, "pdf_text", "Architecture design patterns")

    # Both match "Architecture"
    all_res = db.search("Architecture", only_notes=False)
    assert len(all_res) == 2

    # Only notebook matches when only_notes is True
    notes_res = db.search("Architecture", only_notes=True)
    assert len(notes_res) == 1
    assert notes_res[0]["doc_id"] == note_id
