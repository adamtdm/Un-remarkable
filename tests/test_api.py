"""Tests for FastAPI REST endpoints and web UI serving."""

import pytest
from fastapi.testclient import TestClient

from rmcompanion.config import Settings
from rmcompanion.web.app import create_app


@pytest.fixture
def test_client(tmp_path):
    settings = Settings(data_dir=tmp_path)
    app = create_app(settings=settings)
    with TestClient(app) as client:
        yield client


def test_api_status(test_client):
    res = test_client.get("/api/status")
    assert res.status_code == 200
    data = res.json()
    assert "sync" in data
    assert "blobs_count" in data


def test_api_documents_and_search(test_client):
    # Empty documents initially
    res = test_client.get("/api/documents")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    # Search endpoint
    search_res = test_client.get("/api/search?q=test")
    assert search_res.status_code == 200
    assert isinstance(search_res.json(), list)


def test_static_index_html(test_client):
    res = test_client.get("/")
    assert res.status_code == 200
    assert "reMarkable Companion" in res.text
    assert "<html" in res.text

    # PWA files
    manifest_res = test_client.get("/manifest.json")
    assert manifest_res.status_code == 200
    assert "reMarkable Companion" in manifest_res.json()["name"]

    sw_res = test_client.get("/sw.js")
    assert sw_res.status_code == 200
    assert "rmc-shell" in sw_res.text

    icon_res = test_client.get("/icon.svg")
    assert icon_res.status_code == 200
    assert "<svg" in icon_res.text
