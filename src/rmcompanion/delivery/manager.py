"""Delivery manager orchestrating scheduled newspapers and daily puzzles to reMarkable Cloud."""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
from typing import Any

from rmcompanion.cloud.client import RMCloudClient
from rmcompanion.delivery.models import DeliverySettings
from rmcompanion.delivery.newspaper import DailyNewspaperGenerator
from rmcompanion.delivery.puzzles import DailyPuzzlesGenerator
from rmcompanion.editor.notebook_editor import NotebookEditor
from rmcompanion.store.db import Database
from rmcompanion.sync.engine import SyncEngine

logger = logging.getLogger(__name__)

SETTINGS_KEY = "delivery_settings"


class DeliveryManager:
    """Manages scheduled and on-demand delivery of news and puzzles to tablet."""

    def __init__(
        self,
        db: Database,
        client: RMCloudClient,
        sync_engine: SyncEngine,
        notebook_editor: NotebookEditor | None = None,
    ) -> None:
        self.db = db
        self.client = client
        self.sync_engine = sync_engine
        self.notebook_editor = notebook_editor

    def get_settings(self) -> DeliverySettings:
        """Load delivery configuration from database."""
        raw = self.db.get_state(SETTINGS_KEY, "")
        if not raw:
            return DeliverySettings()
        try:
            data = json.loads(raw)
            return DeliverySettings(**data)
        except Exception as e:
            logger.warning("Error parsing delivery settings: %s", e)
            return DeliverySettings()

    def update_settings(self, settings: DeliverySettings) -> None:
        """Persist delivery configuration."""
        self.db.set_state(SETTINGS_KEY, json.dumps(settings.model_dump()))

    async def ensure_folder(self, folder_name: str) -> str:
        """Find existing folder or create it locally and remotely. Returns folder ID."""
        folder_name = folder_name.strip() or "General"
        # Check if already exists in DB
        folders = self.db.list_documents(file_type="collection", include_deleted=False)
        for f in folders:
            if f.get("visible_name", "").lower() == folder_name.lower():
                return f["id"]

        # If not, create it via notebook editor & cloud
        folder_id = ""
        if self.notebook_editor:
            try:
                folder = self.notebook_editor.create_folder(name=folder_name, parent_id="")
                folder_id = folder["id"]
                # Push to cloud
                await self.sync_engine.create_remote_folder(folder_id, folder_name, parent_id="")
            except Exception as e:
                logger.warning("Error creating delivery folder '%s': %s", folder_name, e)

        return folder_id

    async def deliver_newspaper(self, force: bool = False) -> dict[str, Any]:
        """Generate and upload today's morning newspaper."""
        settings = self.get_settings()
        today_str = datetime.date.today().strftime("%Y-%m-%d")

        if not force and settings.last_news_delivery == today_str:
            return {"status": "already_delivered", "date": today_str}

        logger.info("Generating daily newspaper digest for %s...", today_str)
        pdf_bytes, filename = await DailyNewspaperGenerator.generate_digest(
            rss_feeds=settings.news_rss_feeds,
            include_wikipedia=settings.news_include_wikipedia,
            include_weather=settings.news_include_weather,
            weather_location=settings.news_weather_location,
            device=settings.news_device,
            articles_per_feed=settings.news_articles_per_feed,
            full_body=settings.news_full_body,
        )

        folder_id = await self.ensure_folder(settings.news_folder)

        # Upload directly to reMarkable Cloud
        logger.info("Uploading %s (%d bytes) to reMarkable Cloud folder '%s'...", filename, len(pdf_bytes), settings.news_folder)
        result = await self.client.upload_document(
            file_bytes=pdf_bytes,
            filename=filename,
            parent_id=folder_id,
            file_type="pdf",
        )

        # Update last delivered timestamp
        settings.last_news_delivery = today_str
        self.update_settings(settings)

        # Trigger background sync to mirror locally
        if hasattr(self.sync_engine, "trigger"):
            self.sync_engine.trigger()
        elif hasattr(self.sync_engine, "sync_once"):
            asyncio.create_task(self.sync_engine.sync_once())

        return {
            "status": "success",
            "filename": filename,
            "folder": settings.news_folder,
            "size_bytes": len(pdf_bytes),
            "result": result,
        }

    async def deliver_puzzles(self, force: bool = False) -> dict[str, Any]:
        """Fetch, crop and upload today's crosswords and sudoku puzzles."""
        settings = self.get_settings()
        today_str = datetime.date.today().strftime("%Y-%m-%d")

        if not force and settings.last_puzzles_delivery == today_str:
            return {"status": "already_delivered", "date": today_str}

        folder_id = await self.ensure_folder(settings.puzzles_folder)
        delivered_files: list[str] = []

        # 1. Guardian Quick Crossword
        if settings.puzzles_guardian_quick:
            try:
                pdf_bytes, fn = await DailyPuzzlesGenerator.fetch_guardian_crossword(crossword_type="quick")
                await self.client.upload_document(file_bytes=pdf_bytes, filename=fn, parent_id=folder_id)
                delivered_files.append(fn)
            except Exception as e:
                logger.warning("Could not deliver Guardian Quick crossword: %s", e)

        # 2. Guardian Cryptic Crossword
        if settings.puzzles_guardian_cryptic:
            try:
                pdf_bytes, fn = await DailyPuzzlesGenerator.fetch_guardian_crossword(crossword_type="cryptic")
                await self.client.upload_document(file_bytes=pdf_bytes, filename=fn, parent_id=folder_id)
                delivered_files.append(fn)
            except Exception as e:
                logger.warning("Could not deliver Guardian Cryptic crossword: %s", e)

        # 3. Daily Sudoku
        if settings.puzzles_sudoku:
            try:
                w = 1620 if settings.news_device == "paper_pro" else 1404
                h = 2160 if settings.news_device == "paper_pro" else 1872
                pdf_bytes, fn = DailyPuzzlesGenerator.generate_sudoku_pdf(
                    difficulty=settings.puzzles_sudoku_difficulty,
                    width=w,
                    height=h,
                )
                await self.client.upload_document(file_bytes=pdf_bytes, filename=fn, parent_id=folder_id)
                delivered_files.append(fn)
            except Exception as e:
                logger.warning("Could not deliver Daily Sudoku: %s", e)

        settings.last_puzzles_delivery = today_str
        self.update_settings(settings)

        if hasattr(self.sync_engine, "trigger"):
            self.sync_engine.trigger()
        elif hasattr(self.sync_engine, "sync_once"):
            asyncio.create_task(self.sync_engine.sync_once())

        return {
            "status": "success",
            "delivered_files": delivered_files,
            "folder": settings.puzzles_folder,
        }

    async def check_scheduled_delivery(self) -> None:
        """Called periodically by background sync loop to deliver scheduled news and puzzles."""
        try:
            settings = self.get_settings()
            if not settings.news_enabled and not settings.puzzles_enabled:
                return

            now = datetime.datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            cur_time_str = now.strftime("%H:%M")

            # Check newspaper
            if (
                settings.news_enabled
                and settings.last_news_delivery != today_str
                and cur_time_str >= settings.news_delivery_time
            ):
                logger.info("Scheduled time reached for Daily Newspaper (%s >= %s)", cur_time_str, settings.news_delivery_time)
                await self.deliver_newspaper(force=False)

            # Check puzzles
            if (
                settings.puzzles_enabled
                and settings.last_puzzles_delivery != today_str
                and cur_time_str >= settings.puzzles_delivery_time
            ):
                logger.info("Scheduled time reached for Daily Puzzles (%s >= %s)", cur_time_str, settings.puzzles_delivery_time)
                await self.deliver_puzzles(force=False)

        except Exception as e:
            logger.error("Error during scheduled delivery check: %s", e)
