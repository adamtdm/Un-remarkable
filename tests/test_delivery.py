"""Tests for automated daily newspapers, RSS digests, and crosswords delivery."""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pymupdf

from rmcompanion.delivery.models import DeliverySettings
from rmcompanion.delivery.newspaper import DailyNewspaperGenerator
from rmcompanion.delivery.puzzles import DailyPuzzlesGenerator, crop_pdf_to_content
from rmcompanion.delivery.manager import DeliveryManager


def test_delivery_settings_defaults():
    settings = DeliverySettings()
    assert settings.news_enabled is False
    assert settings.news_folder == "Daily News"
    assert settings.puzzles_enabled is False
    assert settings.puzzles_folder == "Puzzles"
    assert len(settings.news_rss_feeds) > 0


def test_generate_sudoku_pdf():
    pdf_bytes, filename = DailyPuzzlesGenerator.generate_sudoku_pdf(
        difficulty="medium",
        target_date=datetime.date(2026, 11, 1),
        width=1620,
        height=2160,
    )
    assert len(pdf_bytes) > 1000
    assert "Daily_Sudoku_2026-11-01.pdf" == filename

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    assert len(doc) == 2  # Page 1: Puzzle, Page 2: Solution
    assert doc[0].rect.width == 1620
    assert doc[0].rect.height == 2160


def test_crop_pdf_to_content():
    # Create simple dummy PDF with drawings
    doc = pymupdf.open()
    page = doc.new_page(width=600, height=800)
    page.draw_rect(pymupdf.Rect(100, 150, 400, 600), color=(0, 0, 0), fill=(0, 0, 0))
    raw_bytes = doc.tobytes()

    cropped_bytes = crop_pdf_to_content(raw_bytes, margin=10)
    assert len(cropped_bytes) > 0
    cdoc = pymupdf.open(stream=cropped_bytes, filetype="pdf")
    assert cdoc[0].rect.width < 600


@pytest.mark.asyncio
async def test_newspaper_generation_offline():
    # Test generation with empty feeds and no external network calls
    pdf_bytes, filename = await DailyNewspaperGenerator.generate_digest(
        rss_feeds=[],
        include_wikipedia=False,
        include_weather=False,
        device="paper_pro",
        target_date=datetime.date(2026, 11, 1),
    )
    assert len(pdf_bytes) > 500
    assert "Morning_Chronicle_2026-11-01.pdf" == filename
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    assert len(doc) >= 1


def test_delivery_manager_settings(tmp_path):
    from rmcompanion.store.db import Database
    db = Database(db_path=tmp_path / "test.db")
    client = MagicMock()
    sync_engine = MagicMock()

    dm = DeliveryManager(db=db, client=client, sync_engine=sync_engine)
    s = dm.get_settings()
    assert s.news_enabled is False

    s.news_enabled = True
    s.news_weather_location = "Edinburgh"
    dm.update_settings(s)

    s2 = dm.get_settings()
    assert s2.news_enabled is True
    assert s2.news_weather_location == "Edinburgh"
