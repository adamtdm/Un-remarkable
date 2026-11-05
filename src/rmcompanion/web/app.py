"""FastAPI application factory mounting REST APIs, MCP endpoint, and web UI."""

from __future__ import annotations

import contextlib
import logging
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response
from mcp.server.transport_security import TransportSecuritySettings

from rmcompanion.cloud.auth import AuthManager
from rmcompanion.cloud.client import RMCloudClient
from rmcompanion.config import Settings, get_settings
from rmcompanion.converter.engine import ConverterEngine
from rmcompanion.delivery.manager import DeliveryManager
from rmcompanion.editor.notebook_editor import NotebookEditor
from rmcompanion.index.text_indexer import TextIndexer
from rmcompanion.intelligence.provider import get_vision_provider
from rmcompanion.intelligence.task_extractor import TaskExtractor
from rmcompanion.mcp.server import create_mcp_server
from rmcompanion.render.exporter import Exporter
from rmcompanion.store.blob_store import BlobStore
from rmcompanion.store.db import Database
from rmcompanion.sync.engine import SyncEngine
from rmcompanion.web.api import get_router

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the primary FastAPI application."""
    app_settings = settings or get_settings()

    db = Database(settings=app_settings)
    blob_store = BlobStore(settings=app_settings)
    auth = AuthManager(settings=app_settings)
    client = RMCloudClient(auth=auth, settings=app_settings)
    text_indexer = TextIndexer(db=db, blob_store=blob_store)

    sync_engine = SyncEngine(
        client=client,
        db=db,
        blob_store=blob_store,
        auth=auth,
        settings=app_settings,
        on_doc_indexed=text_indexer.index_document,
    )

    exporter = Exporter(db=db, blob_store=blob_store, settings=app_settings)
    converter_engine = ConverterEngine(
        db=db, blob_store=blob_store, settings=app_settings, sync_engine=sync_engine
    )

    vision_provider = get_vision_provider(db, settings=app_settings)
    task_extractor = TaskExtractor(
        db=db,
        blob_store=blob_store,
        exporter=exporter,
        vision_provider=vision_provider,
    )

    notebook_editor = NotebookEditor(
        db=db,
        blob_store=blob_store,
        task_extractor=task_extractor,
    )

    delivery_manager = DeliveryManager(
        db=db,
        client=client,
        sync_engine=sync_engine,
        notebook_editor=notebook_editor,
    )
    sync_engine.delivery_manager = delivery_manager

    # Initialize MCP Server
    mcp_server = create_mcp_server(
        db=db,
        blob_store=blob_store,
        exporter=exporter,
        sync_engine=sync_engine,
        task_extractor=task_extractor,
        notebook_editor=notebook_editor,
        settings=app_settings,
    )

    # Create streamable HTTP app for MCP
    mcp_asgi = mcp_server.streamable_http_app(
        streamable_http_path="/",
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("Initializing reMarkable Companion on port %d...", app_settings.port)
        sync_engine.start_background_loop()
        async with mcp_server.session_manager.run():
            yield
        sync_engine.stop()
        logger.info("reMarkable Companion stopped")

    app = FastAPI(
        title="reMarkable Companion",
        description="Local cloud mirror, dark mode web reader, and MCP server for reMarkable devices (Paper Pro, RM2, RM1)",
        version="0.1.1",
        lifespan=lifespan,
    )

    app.state.db = db
    app.state.blob_store = blob_store
    app.state.auth = auth
    app.state.client = client
    app.state.sync_engine = sync_engine
    app.state.exporter = exporter
    app.state.converter_engine = converter_engine
    app.state.text_indexer = text_indexer
    app.state.task_extractor = task_extractor
    app.state.notebook_editor = notebook_editor
    app.state.delivery_manager = delivery_manager

    # CORS support for local and remote access
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount REST API
    api_router = get_router(
        db=db,
        blob_store=blob_store,
        auth=auth,
        sync_engine=sync_engine,
        exporter=exporter,
        converter_engine=converter_engine,
        text_indexer=text_indexer,
        task_extractor=task_extractor,
        notebook_editor=notebook_editor,
        settings=app_settings,
        delivery_manager=delivery_manager,
    )
    app.include_router(api_router)

    # Mount MCP endpoint
    app.mount("/mcp", mcp_asgi)

    # Mount Static Web Assets with Cache-Control headers
    static_dir = Path(__file__).parent / "static"
    if not static_dir.is_dir():
        for candidate in [
            Path("/app/src/rmcompanion/web/static"),
            Path("./src/rmcompanion/web/static"),
        ]:
            if candidate.is_dir():
                static_dir = candidate
                break

    class CacheBustingStaticFiles(StaticFiles):
        async def get_response(self, path: str, scope: Any) -> Response:
            response = await super().get_response(path, scope)
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            return response

    if static_dir.is_dir():
        app.mount("/", CacheBustingStaticFiles(directory=str(static_dir), html=True), name="static")

    return app
