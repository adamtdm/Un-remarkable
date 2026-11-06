"""CLI entry points for running server, one-off sync, and MCP stdio."""

from __future__ import annotations

import argparse
import asyncio
import logging

import uvicorn

from rmcompanion.cloud.auth import AuthManager
from rmcompanion.cloud.client import RMCloudClient
from rmcompanion.config import get_settings
from rmcompanion.index.text_indexer import TextIndexer
from rmcompanion.mcp.server import create_mcp_server
from rmcompanion.render.exporter import Exporter
from rmcompanion.store.blob_store import BlobStore
from rmcompanion.store.db import Database
from rmcompanion.sync.engine import SyncEngine


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def cmd_run(args: argparse.Namespace) -> None:
    settings = get_settings()
    if args.host:
        settings.host = args.host
    if args.port:
        settings.port = args.port

    setup_logging(settings.log_level)
    from rmcompanion.web.app import create_app

    app = create_app(settings)
    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level.lower())


def cmd_sync(args: argparse.Namespace) -> None:
    settings = get_settings()
    setup_logging("INFO")

    async def _do_sync() -> None:
        db = Database(settings=settings)
        blob_store = BlobStore(settings=settings)
        auth = AuthManager(settings=settings)
        client = RMCloudClient(auth=auth, settings=settings)
        text_indexer = TextIndexer(db=db, blob_store=blob_store)
        engine = SyncEngine(
            client=client,
            db=db,
            blob_store=blob_store,
            auth=auth,
            settings=settings,
            on_doc_indexed=text_indexer.index_document,
        )

        res = await engine.sync_once()
        print(f"Sync result: {res}")

    asyncio.run(_do_sync())


def cmd_mcp(args: argparse.Namespace) -> None:
    settings = get_settings()
    setup_logging("WARNING")

    async def _run_mcp() -> None:
        db = Database(settings=settings)
        blob_store = BlobStore(settings=settings)
        exporter = Exporter(db=db, blob_store=blob_store, settings=settings)
        # No background loop here: the sync engine is only used to push MCP edits to the cloud.
        sync_engine = SyncEngine(db=db, blob_store=blob_store, settings=settings, exporter=exporter)
        server = create_mcp_server(
            db=db, blob_store=blob_store, exporter=exporter, sync_engine=sync_engine, settings=settings
        )
        await server.run_stdio_async()

    asyncio.run(_run_mcp())


def cmd_auth(args: argparse.Namespace) -> None:
    settings = get_settings()
    setup_logging("INFO")
    code = args.code.strip()

    async def _do_auth() -> None:
        auth = AuthManager(settings=settings)
        await auth.register_device(code)
        print("Device paired successfully! Device token received.")

    asyncio.run(_do_auth())


def main() -> None:
    parser = argparse.ArgumentParser(description="reMarkable Companion CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # run command
    run_parser = subparsers.add_parser("run", help="Start web app and sync daemon (default)")
    run_parser.add_argument("--host", type=str, default=None, help="Host to bind")
    run_parser.add_argument("--port", type=int, default=None, help="Port to listen on")

    # sync command
    subparsers.add_parser("sync", help="Trigger a single sync cycle")

    # mcp command
    subparsers.add_parser("mcp", help="Run MCP server over stdio for AI integration")

    # auth command
    auth_parser = subparsers.add_parser("auth", help="Pair device using an 8-character code")
    auth_parser.add_argument("code", type=str, help="8-character code from my.remarkable.com")

    args = parser.parse_args()

    if args.command == "sync":
        cmd_sync(args)
    elif args.command == "mcp":
        cmd_mcp(args)
    elif args.command == "auth":
        cmd_auth(args)
    else:
        cmd_run(args)


if __name__ == "__main__":
    main()
