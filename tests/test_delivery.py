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
from rmcompanion.delivery.rss_directory import (
    CATEGORIES,
    POPULAR_FEEDS,
    PRESETS,
    discover_feed_url,
    search_popular_feeds,
    validate_feed,
)


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


def test_rss_directory_catalog_and_search():
    assert len(CATEGORIES) >= 5
    assert len(POPULAR_FEEDS) >= 20
    assert len(PRESETS) >= 4

    # Search with query
    results = search_popular_feeds(query="verge")
    assert any("verge" in r["name"].lower() for r in results)

    # Search by category
    tech_results = search_popular_feeds(category="Tech")
    assert all(r["category"].lower() == "tech" for r in tech_results)
    assert len(tech_results) >= 4


@pytest.mark.asyncio
async def test_rss_validate_and_discover_mocked():
    sample_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Sample News</title>
        <description>Breaking mock stories</description>
        <item>
          <title>First Headline</title>
          <link>https://example.com/1</link>
        </item>
      </channel>
    </rss>"""

    with patch("httpx.AsyncClient.get") as mock_get:
        import httpx
        mock_get.return_value = httpx.Response(200, content=sample_xml)
        val = await validate_feed("https://example.com/rss.xml")
        assert val["valid"] is True
        assert val["title"] == "Sample News"
        assert len(val["articles"]) == 1
        assert val["articles"][0]["title"] == "First Headline"

    # Test auto-discovery via HTML
    sample_html = """<!DOCTYPE html><html><head>
      <title>Example Blog</title>
      <link rel="alternate" type="application/rss+xml" title="Feed" href="/feed.xml">
    </head><body></body></html>"""

    with patch("httpx.AsyncClient.get") as mock_get:
        # First call HTML page, second call XML feed validation
        req = httpx.Request("GET", "https://example.com")
        feed_req = httpx.Request("GET", "https://example.com/feed.xml")
        mock_get.side_effect = [
            httpx.Response(200, text=sample_html, headers={"content-type": "text/html"}, request=req),
            httpx.Response(200, content=sample_xml, headers={"content-type": "application/rss+xml"}, request=feed_req),
        ]
        disc = await discover_feed_url("https://example.com")
        assert len(disc) == 1
        assert disc[0]["url"] == "https://example.com/feed.xml"
        assert disc[0]["title"] == "Sample News"


def test_rss_api_endpoints():
    from fastapi.testclient import TestClient
    from rmcompanion.web.app import create_app
    from rmcompanion.config import Settings

    app = create_app(Settings())
    client = TestClient(app)

    # 1. Catalog endpoint
    res = client.get("/api/delivery/rss/catalog")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "categories" in data
    assert "presets" in data
    assert len(data["feeds"]) > 0

    # 2. Search query filter
    res_search = client.get("/api/delivery/rss/catalog?query=guardian")
    assert res_search.status_code == 200
    data_search = res_search.json()
    assert any("guardian" in f["name"].lower() for f in data_search["feeds"])


@pytest.mark.asyncio
async def test_article_extractor():
    from rmcompanion.delivery.article_extractor import extract_article_content
    import httpx

    # 1. Fallback when URL empty
    async with httpx.AsyncClient() as client:
        res = await extract_article_content(
            client=client,
            url="",
            rss_title="Headline Story",
            rss_summary="A short summary of breaking events.",
            source="Test Agency",
        )
        assert res["title"] == "Headline Story"
        assert res["is_full_text"] is False
        assert len(res["paragraphs"]) == 2
        assert "A short summary" in res["paragraphs"][0]["text"]

    # 2. HTML article extraction
    sample_article_html = """<!DOCTYPE html><html><body>
      <nav><a href="/">Home</a></nav>
      <article>
        <h1>Headline</h1>
        <p>Sign up for our newsletter to get updates.</p>
        <p>This is the first substantive paragraph detailing major discoveries in astrophysics and stellar dynamics.</p>
        <h2>Deeper Analysis</h2>
        <p>Here is another substantial paragraph with thorough research observations and experimental measurements.</p>
      </article>
      <footer>All rights reserved.</footer>
    </body></html>"""

    with patch("httpx.AsyncClient.get") as mock_get:
        req = httpx.Request("GET", "https://example.com/article1")
        mock_get.return_value = httpx.Response(200, text=sample_article_html, request=req)
        async with httpx.AsyncClient() as client:
            res = await extract_article_content(
                client=client,
                url="https://example.com/article1",
                rss_title="Astrophysics Discovery",
                rss_summary="Summary",
                source="Nature",
                category="Science & Space Exploration",
            )
            assert res["is_full_text"] is True
            assert res["category"] == "Science & Space Exploration"
            assert len(res["paragraphs"]) >= 2
            # Verify newsletter boilerplate was filtered out
            assert not any("Sign up for our newsletter" in p["text"] for p in res["paragraphs"])


@pytest.mark.asyncio
async def test_sectioned_newspaper_with_toc_and_jump_links():
    mock_articles = [
        {
            "title": "Global Rail Network Expansion Announced",
            "source": "BBC News",
            "category": "World & National News",
            "url": "https://example.com/bbc-rail",
            "reading_time_min": 3,
            "word_count": 650,
            "paragraphs": [
                {"type": "p", "text": "Governments across the continent have formally signed an accord committing billions in infrastructure spending."},
                {"type": "h2", "text": "Cross-Border High-Speed Lines"},
                {"type": "p", "text": "The initial phase will connect major metropolitan centers with carbon-neutral electric trains operating at over 300 km/h."},
            ],
            "is_full_text": True,
        },
        {
            "title": "Quantum Computing Platform Opens to Public Preview",
            "source": "The Verge",
            "category": "Technology & Computing",
            "url": "https://example.com/verge-quantum",
            "reading_time_min": 4,
            "word_count": 820,
            "paragraphs": [
                {"type": "p", "text": "Engineers have unveiled a fault-tolerant logical qubit platform available via cloud APIs for developers worldwide."},
                {"type": "h2", "text": "Error Correction Benchmarks"},
                {"type": "p", "text": "In preliminary benchmarks, the system demonstrated error rates orders of magnitude below existing noisy intermediate-scale hardware."},
            ],
            "is_full_text": True,
        },
    ]

    with patch.object(DailyNewspaperGenerator, "_fetch_all_feeds", new_callable=AsyncMock) as mock_feeds, \
         patch.object(DailyNewspaperGenerator, "_fetch_full_articles", new_callable=AsyncMock) as mock_full, \
         patch.object(DailyNewspaperGenerator, "_fetch_weather", new_callable=AsyncMock) as mock_weather, \
         patch.object(DailyNewspaperGenerator, "_fetch_wikipedia", new_callable=AsyncMock) as mock_wiki:

        mock_feeds.return_value = [{"title": "dummy", "source": "dummy", "category": "dummy", "link": "dummy"}]
        mock_full.return_value = mock_articles
        mock_weather.return_value = "London: 15°C, Partly Cloudy"
        mock_wiki.return_value = ({"title": "Apollo 11", "extract": "Apollo 11 was the American spaceflight that first landed humans on the Moon."}, ["1969: Moon landing"])

        pdf_bytes, filename = await DailyNewspaperGenerator.generate_digest(
            rss_feeds=["https://example.com/rss"],
            include_wikipedia=True,
            include_weather=True,
            device="paper_pro",
            target_date=datetime.date(2026, 11, 4),
            articles_per_feed=2,
            full_body=True,
        )

        assert len(pdf_bytes) > 2000
        assert "Morning_Chronicle_2026-11-04.pdf" == filename

        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        # Page 1: Front Page; Pages 2, 3: Articles
        assert len(doc) >= 3

        # Check Page 0 (Front Page) has Table of Contents jump links
        p0_links = list(doc[0].get_links())
        assert len(p0_links) >= 2  # Links to Page 1 and Page 2
        target_pages = {lnk["page"] for lnk in p0_links}
        assert 1 in target_pages
        assert 2 in target_pages

        # Check Page 1 (First Article) has a back link to Page 0
        p1_links = list(doc[1].get_links())
        assert len(p1_links) >= 1
        assert p1_links[0]["page"] == 0

        # Check Page 2 (Second Article) has a back link to Page 0
        p2_links = list(doc[2].get_links())
        assert len(p2_links) >= 1
        assert p2_links[0]["page"] == 0

