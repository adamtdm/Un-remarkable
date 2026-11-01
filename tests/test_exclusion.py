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

    # Un-exclude the folder
    affected_unexclude = db.set_exclude_from_search(folder_id, False)
    assert folder_id in affected_unexclude
    assert doc_id in affected_unexclude
    assert not db.is_excluded_from_search(folder_id)
    assert not db.is_excluded_from_search(doc_id)


def test_api_recursive_unexclusion_reindexing(tmp_path):
    import hashlib
    import pymupdf
    from fastapi.testclient import TestClient

    from rmcompanion.config import Settings
    from rmcompanion.web.app import create_app

    settings = Settings(data_dir=tmp_path)
    app = create_app(settings=settings)
    client = TestClient(app)

    db = app.state.db
    blob_store = app.state.blob_store

    # 1. Create a dummy PDF with text
    doc_pdf = pymupdf.open()
    p = doc_pdf.new_page()
    p.insert_text((50, 50), "Classified superhero research secret", fontsize=16)
    pdf_bytes = doc_pdf.tobytes()
    doc_pdf.close()

    # 2. Store blob
    pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
    blob_store.put(pdf_hash, pdf_bytes, verify=False)

    # 3. Insert folder and child document
    folder_id = "fld-classified-1"
    doc_id = "doc-hero-dossier-2"
    doc_hash = "dochash123"

    db.upsert_document({
        "id": folder_id,
        "visible_name": "Classified Folder",
        "type": "CollectionType",
        "parent_id": "",
    })
    db.upsert_document({
        "id": doc_id,
        "visible_name": "Hero Dossier",
        "type": "DocumentType",
        "file_type": "pdf",
        "parent_id": folder_id,
        "doc_hash": doc_hash,
    })
    db.set_document_files(
        doc_hash,
        [{"file_id": f"{doc_id}.pdf", "blob_hash": pdf_hash, "file_type": "pdf", "size": len(pdf_bytes)}],
    )

    # Index text initial
    app.state.text_indexer.index_document(doc_id, doc_hash)

    # Search finds it
    res = client.get("/api/search?q=superhero").json()
    assert len(res) >= 1
    assert any(r["doc_id"] == doc_id for r in res)

    # Exclude the folder via API
    exc_res = client.post(f"/api/documents/{folder_id}/exclude-search", json={"exclude": True})
    assert exc_res.status_code == 200
    assert exc_res.json()["affected_count"] == 2

    # Body text is purged from index; searching "superhero" returns 0 hits
    search_exc = client.get("/api/search?q=superhero").json()
    assert len(search_exc) == 0

    # Un-exclude the folder via API
    unexc_res = client.post(f"/api/documents/{folder_id}/exclude-search", json={"exclude": False})
    assert unexc_res.status_code == 200
    assert unexc_res.json()["affected_count"] == 2

    # Now child document is automatically re-indexed and searchable again
    search_restored = client.get("/api/search?q=superhero").json()
    assert len(search_restored) >= 1
    assert search_restored[0]["doc_id"] == doc_id


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


def test_task_exclusion_with_document_and_folder(tmp_path):
    db_file = tmp_path / "test.db"
    db = Database(db_path=db_file)

    folder_id = "f-work"
    doc_id = "doc-work-notes"

    db.upsert_document({"id": folder_id, "visible_name": "Work", "type": "CollectionType", "parent_id": ""})
    db.upsert_document({"id": doc_id, "visible_name": "Meeting", "type": "DocumentType", "parent_id": folder_id})

    # Add tasks
    db.upsert_task({
        "id": "t-1",
        "doc_id": doc_id,
        "page_idx": 0,
        "raw_text": "* Buy notebook",
        "clean_text": "Buy notebook",
        "status": "open",
        "marker_type": "star",
        "fingerprint": "fp1",
    })

    assert db.count_open_tasks() == 1
    assert len(db.list_tasks()) == 1

    # Exclude parent folder
    db.set_exclude_from_search(folder_id, True)

    # Tasks for documents inside the excluded folder must not appear in the task list
    assert db.count_open_tasks() == 0
    assert len(db.list_tasks()) == 0


def test_hierarchical_subfolder_exclusion(tmp_path):
    """Excluding a root folder must exclude subfolders and deep nested documents."""
    db_file = tmp_path / "test.db"
    db = Database(db_path=db_file)

    root_id = "folder-root"
    sub_id = "folder-sub"
    doc_id = "doc-nested"

    db.upsert_document({"id": root_id, "visible_name": "Root", "type": "CollectionType", "parent_id": ""})
    db.upsert_document({"id": sub_id, "visible_name": "Sub", "type": "CollectionType", "parent_id": root_id})
    db.upsert_document({"id": doc_id, "visible_name": "Doc", "type": "DocumentType", "file_type": "pdf", "parent_id": sub_id})

    # Initially none are excluded
    assert not db.is_excluded_from_search(root_id)
    assert not db.is_excluded_from_search(sub_id)
    assert not db.is_excluded_from_search(doc_id)

    # Exclude root folder
    affected = db.set_exclude_from_search(root_id, True)
    assert root_id in affected
    assert sub_id in affected
    assert doc_id in affected

    # Check that all are marked excluded
    assert db.is_excluded_from_search(root_id)
    assert db.is_excluded_from_search(sub_id)
    assert db.is_excluded_from_search(doc_id)

    # Database records must have exclude_from_search = 1
    assert db.get_document(root_id)["exclude_from_search"] is True
    assert db.get_document(sub_id)["exclude_from_search"] is True
    assert db.get_document(doc_id)["exclude_from_search"] is True

    # list_documents must report effective_exclude
    docs = db.list_documents(parent_id=sub_id)
    assert len(docs) == 1
    assert docs[0]["effective_exclude"] is True

    # get_folder_tree must report effective_exclude
    tree = db.get_folder_tree()
    sub_folder_item = next(f for f in tree if f["id"] == sub_id)
    assert sub_folder_item["effective_exclude"] is True
    assert sub_folder_item["exclude_from_search"] is True

    # Un-excluding root folder restores all
    db.set_exclude_from_search(root_id, False)
    assert not db.is_excluded_from_search(root_id)
    assert not db.is_excluded_from_search(sub_id)
    assert not db.is_excluded_from_search(doc_id)


