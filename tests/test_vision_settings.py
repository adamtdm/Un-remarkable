"""Tests for live vision models discovery, Gemini API key resolution, and container environment fallback."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from rmcompanion.config import Settings
from rmcompanion.intelligence.provider import (
    VisionProvider,
    get_effective_vision_config,
    get_vision_provider,
)
from rmcompanion.store.db import Database
from rmcompanion.web.app import create_app


def test_vision_config_reads_env_vars(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyTestFromEnv123456789")
    monkeypatch.setenv("VISION_MODEL", "gemini-flash-lite-latest")
    monkeypatch.setenv("VISION_PROVIDER", "gemini")

    settings = Settings(data_dir=tmp_path)
    assert settings.gemini_api_key == "AIzaSyTestFromEnv123456789"
    assert settings.vision_model == "gemini-flash-lite-latest"
    assert settings.vision_provider == "gemini"

    db = Database(settings=settings)
    conf = get_effective_vision_config(db, settings=settings)
    assert conf["provider"] == "gemini"
    assert conf["api_key"] == "AIzaSyTestFromEnv123456789"
    assert conf["api_key_source"] == "environment"
    assert conf["model"] == "gemini-flash-lite-latest"

    vp = get_vision_provider(db, settings=settings)
    assert vp is not None
    assert vp.api_key == "AIzaSyTestFromEnv123456789"
    assert vp.model == "gemini-flash-lite-latest"


def test_database_overrides_environment_vars(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyFromEnv")
    settings = Settings(data_dir=tmp_path)
    db = Database(settings=settings)

    # Save custom DB override
    db.set_state("vision_settings", json.dumps({
        "provider": "gemini",
        "api_key": "AIzaSyFromDatabaseCustom",
        "model": "gemini-flash-lite-latest",
        "base_url": "",
    }))

    conf = get_effective_vision_config(db, settings=settings)
    assert conf["api_key"] == "AIzaSyFromDatabaseCustom"
    assert conf["api_key_source"] == "database"
    assert conf["model"] == "gemini-flash-lite-latest"


def test_api_vision_settings_endpoint_with_env(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyTestSecret1234")
    settings = Settings(data_dir=tmp_path)
    app = create_app(settings=settings)
    client = TestClient(app)

    # GET /api/settings/vision should reflect the environment key
    res = client.get("/api/settings/vision")
    assert res.status_code == 200
    data = res.json()
    assert data["api_key_set"] is True
    assert data["api_key_source"] == "environment"
    assert "AIza" in data["api_key_masked"]
    assert data["model"] == "gemini-flash-lite-latest"


def test_models_fallback_includes_gemini_flash_lite_latest(tmp_path):
    settings = Settings(data_dir=tmp_path)
    app = create_app(settings=settings)
    client = TestClient(app)

    # GET request without API key returns fallback containing gemini-flash-lite-latest
    res = client.get("/api/settings/vision/models?provider=gemini")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["provider"] == "gemini"
    assert data["default_model"] == "gemini-flash-lite-latest"

    model_ids = [m["id"] for m in data["models"]]
    assert "gemini-flash-lite-latest" in model_ids
    assert data["models"][0]["id"] == "gemini-flash-lite-latest"
    assert data["models"][0]["is_recommended"] is True


def test_live_gemini_models_discovery_does_not_exclude_latest(tmp_path):
    """Ensure -latest models (like gemini-flash-lite-latest) are not stripped out by filter."""
    settings = Settings(data_dir=tmp_path)
    app = create_app(settings=settings)
    client = TestClient(app)

    mock_gemini_response = {
        "models": [
            {
                "name": "models/gemini-flash-lite-latest",
                "displayName": "Gemini Flash Lite Latest",
                "supportedGenerationMethods": ["generateContent"],
            },
            {
                "name": "models/gemini-3.5-flash-lite",
                "displayName": "Gemini 3.5 Flash Lite",
                "supportedGenerationMethods": ["generateContent"],
            },
            {
                "name": "models/gemini-3.8-flash",
                "displayName": "Gemini 3.8 Flash",
                "supportedGenerationMethods": ["generateContent"],
            },
            {
                "name": "models/gemini-2.0-flash",
                "displayName": "Deprecated Gemini 2.0 Flash",
                "supportedGenerationMethods": ["generateContent"],
            },
        ]
    }

    mock_resp = httpx.Response(200, json=mock_gemini_response, request=httpx.Request("GET", "https://generativelanguage.googleapis.com"))

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=mock_resp):
        res = client.post("/api/settings/vision/models", json={
            "provider": "gemini",
            "api_key": "AIzaFakeValidKey",
            "model": "gemini-flash-lite-latest",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["ok"] is True
        assert data["live"] is True
        model_ids = [m["id"] for m in data["models"]]
        assert "gemini-flash-lite-latest" in model_ids
        assert "gemini-3.5-flash-lite" in model_ids
        assert "gemini-3.8-flash" in model_ids
        # Ensure deprecated 2.0 model is filtered out per gemini-api-dev skill
        assert "gemini-2.0-flash" not in model_ids
        # gemini-flash-lite-latest must be the recommended first option
        assert data["models"][0]["id"] == "gemini-flash-lite-latest"
        assert data["models"][0]["is_recommended"] is True


def test_live_openai_and_ollama_discovery(tmp_path):
    settings = Settings(data_dir=tmp_path)
    app = create_app(settings=settings)
    client = TestClient(app)

    # Mock Ollama tags endpoint
    mock_ollama_tags = {
        "models": [
            {"name": "llama3.2-vision:latest"},
            {"name": "mistral:latest"},
        ]
    }
    mock_resp = httpx.Response(200, json=mock_ollama_tags, request=httpx.Request("GET", "http://localhost:11434"))

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=mock_resp):
        res = client.get("/api/settings/vision/models?provider=ollama&base_url=http://localhost:11434&force_refresh=true")
        assert res.status_code == 200
        data = res.json()
        assert data["ok"] is True
        model_ids = [m["id"] for m in data["models"]]
        assert "llama3.2-vision:latest" in model_ids


def test_connection_test_uses_env_key(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaTestEnvKey")
    settings = Settings(data_dir=tmp_path)
    app = create_app(settings=settings)
    client = TestClient(app)

    mock_resp = httpx.Response(200, json={
        "candidates": [{"content": {"parts": [{"text": "OK"}]}}]
    }, request=httpx.Request("POST", "https://generativelanguage.googleapis.com"))

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_resp):
        # Post test with empty api_key: backend should automatically use the env key
        res = client.post("/api/settings/vision/test", json={
            "provider": "gemini",
            "api_key": "",
            "model": "gemini-flash-lite-latest",
        })
        assert res.status_code == 200
        assert res.json()["ok"] is True
        assert res.json()["reply"] == "OK"
        assert res.json()["model"] == "gemini-flash-lite-latest"
