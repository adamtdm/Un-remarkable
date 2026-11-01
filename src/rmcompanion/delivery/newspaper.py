"""Curated daily newspaper and RSS digest generator."""

from __future__ import annotations

import datetime
import html
import io
import logging
import re
import xml.etree.ElementTree as ET
from typing import Any

import httpx
import pymupdf

logger = logging.getLogger(__name__)


def clean_html(raw_html: str) -> str:
    """Strip HTML tags and unescape entities for clean plain text."""
    if not raw_html:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = html.unescape(text)
    return " ".join(text.split())


class DailyNewspaperGenerator:
    """Assembles a multi-column print newspaper digest PDF for reMarkable."""

    @classmethod
    async def generate_digest(
        cls,
        rss_feeds: list[str],
        include_wikipedia: bool = True,
        include_weather: bool = True,
        weather_location: str = "London",
        device: str = "paper_pro",  # 'paper_pro' (1620x2160) or 'rm2' (1404x1872)
        target_date: datetime.date | None = None,
    ) -> tuple[bytes, str]:
        """Fetch news feeds, Wikipedia, and weather to build the daily newspaper PDF."""
        date = target_date or datetime.date.today()
        width = 1620 if device == "paper_pro" else 1404
        height = 2160 if device == "paper_pro" else 1872

        # 1. Fetch content concurrently
        weather_str = ""
        if include_weather and weather_location:
            weather_str = await cls._fetch_weather(weather_location)

        wiki_article: dict[str, Any] | None = None
        on_this_day: list[str] = []
        if include_wikipedia:
            wiki_article, on_this_day = await cls._fetch_wikipedia(date)

        feed_articles = await cls._fetch_all_feeds(rss_feeds)

        # 2. Render Document
        doc = pymupdf.open()

        # Page 1: Masthead & Lead Story (Wikipedia Featured Article + On This Day)
        p1 = doc.new_page(width=width, height=height)
        cls._render_masthead(p1, date, weather_str, width)
        y_cursor = 250

        if wiki_article:
            y_cursor = cls._render_lead_story(p1, wiki_article, y_cursor, width, height)

        if on_this_day:
            cls._render_on_this_day(p1, on_this_day, y_cursor, width, height)

        cls._render_footer(p1, 1, width, height)

        # Page 2+: Dispatches from RSS Feeds in 2-Column Newspaper Layout
        if feed_articles:
            cls._render_feed_pages(doc, feed_articles, date, width, height)

        # Ensure at least 1 page has footer
        for idx, page in enumerate(doc):
            cls._render_footer(page, idx + 1, width, height, total_pages=len(doc))

        filename = f"Morning_Chronicle_{date.strftime('%Y-%m-%d')}.pdf"
        return doc.tobytes(), filename

    @classmethod
    async def _fetch_weather(cls, location: str) -> str:
        """Fetch current weather string from wttr.in."""
        try:
            loc = location.strip().replace(" ", "+")
            url = f"https://wttr.in/{loc}?format=j1"
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    curr = data["current_condition"][0]
                    temp = curr.get("temp_C", "")
                    desc = curr["weatherDesc"][0].get("value", "")
                    return f"{location}: {temp}°C, {desc}"
        except Exception as e:
            logger.debug("Weather fetch skipped: %s", e)
        return ""

    @classmethod
    async def _fetch_wikipedia(cls, date: datetime.date) -> tuple[dict[str, Any] | None, list[str]]:
        """Fetch Wikipedia's Today's Featured Article and On This Day events."""
        wiki_article: dict[str, Any] | None = None
        on_this_day: list[str] = []
        try:
            url = f"https://en.wikipedia.org/api/rest_v1/feed/featured/{date.year}/{date.month:02d}/{date.day:02d}"
            headers = {"User-Agent": "Un-remarkable/0.1.0 (reMarkable Cloud Companion; mailto:admin@example.com)"}
            async with httpx.AsyncClient(timeout=6.0, headers=headers) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    tfa = data.get("tfa")
                    if tfa:
                        wiki_article = {
                            "title": tfa.get("title", ""),
                            "description": tfa.get("description", ""),
                            "extract": tfa.get("extract", ""),
                        }
                    otd = data.get("onthisday", [])
                    for item in otd[:4]:
                        year = item.get("year", "")
                        text = item.get("text", "")
                        if year and text:
                            on_this_day.append(f"{year}: {text}")
        except Exception as e:
            logger.debug("Wikipedia fetch skipped: %s", e)
        return wiki_article, on_this_day

    @classmethod
    async def _fetch_all_feeds(cls, feeds: list[str]) -> list[dict[str, str]]:
        """Fetch articles from multiple RSS/Atom feeds."""
        articles: list[dict[str, str]] = []
        headers = {"User-Agent": "Un-remarkable/0.1.0 (reMarkable Companion RSS Reader)"}

        async with httpx.AsyncClient(timeout=8.0, headers=headers, follow_redirects=True) as client:
            for feed_url in feeds:
                url = feed_url.strip()
                if not url:
                    continue
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        root = ET.fromstring(resp.content)
                        # Channel info
                        channel = root.find("channel")
                        source_name = "News Dispatch"
                        if channel is not None and channel.find("title") is not None:
                            source_name = channel.find("title").text or source_name

                        # Extract items
                        items = root.findall(".//item")
                        if not items:
                            items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

                        for item in items[:6]:
                            title_el = item.find("title") if item.find("title") is not None else item.find("{http://www.w3.org/2005/Atom}title")
                            desc_el = (
                                item.find("description")
                                if item.find("description") is not None
                                else item.find("{http://www.w3.org/2005/Atom}summary")
                            )
                            title = clean_html(title_el.text if title_el is not None else "")
                            desc = clean_html(desc_el.text if desc_el is not None else "")
                            if title:
                                articles.append({
                                    "source": source_name,
                                    "title": title,
                                    "summary": desc,
                                })
                except Exception as e:
                    logger.warning("Error fetching RSS feed %s: %s", url, e)

        return articles

    @classmethod
    def _render_masthead(cls, page: pymupdf.Page, date: datetime.date, weather: str, width: int) -> None:
        """Draw the newspaper masthead with authentic serif styling."""
        margin_x = 90

        # Top double rules
        page.draw_line((margin_x, 80), (width - margin_x, 80), width=2.5, color=(0, 0, 0))
        page.draw_line((margin_x, 86), (width - margin_x, 86), width=0.8, color=(0, 0, 0))

        # Main Title
        title_text = "THE MORNING CHRONICLE"
        page.insert_text((margin_x, 155), title_text, fontsize=52, fontname="times-bold", color=(0, 0, 0))

        # Subtitle rule
        page.draw_line((margin_x, 178), (width - margin_x, 178), width=1.0, color=(0, 0, 0))

        # Date, edition, and weather row
        date_str = date.strftime("%A, %B %d, %Y")
        meta_parts = [date_str.upper(), "DAILY E-INK EDITION"]
        if weather:
            meta_parts.append(weather.upper())
        meta_text = "   •   ".join(meta_parts)

        page.insert_text((margin_x, 206), meta_text, fontsize=16, fontname="helv", color=(0.25, 0.25, 0.25))
        page.draw_line((margin_x, 222), (width - margin_x, 222), width=1.8, color=(0, 0, 0))

    @classmethod
    def _render_lead_story(
        cls,
        page: pymupdf.Page,
        article: dict[str, Any],
        y_top: int,
        width: int,
        height: int,
    ) -> int:
        """Render the Wikipedia Featured Article of the Day on Page 1."""
        margin_x = 90
        content_w = width - 2 * margin_x

        # Category eyebrow
        page.insert_text(
            (margin_x, y_top + 22),
            "WIKIPEDIA ESSENTIAL KNOWLEDGE  •  FEATURED ARTICLE OF THE DAY",
            fontsize=15,
            fontname="helv",
            color=(0.3, 0.3, 0.3),
        )

        # Headline
        title = article.get("title", "Featured Article")
        rect_title = pymupdf.Rect(margin_x, y_top + 36, width - margin_x, y_top + 140)
        page.insert_textbox(rect_title, title, fontsize=36, fontname="times-bold", color=(0, 0, 0))

        # Divider under headline
        page.draw_line((margin_x, y_top + 145), (width - margin_x, y_top + 145), width=0.8, color=(0.4, 0.4, 0.4))

        # Article body text in 2 balanced columns
        col_gap = 50
        col_w = (content_w - col_gap) / 2
        body_y0 = y_top + 170
        body_y1 = min(body_y0 + 750, height - 420)

        r_col1 = pymupdf.Rect(margin_x, body_y0, margin_x + col_w, body_y1)
        r_col2 = pymupdf.Rect(margin_x + col_w + col_gap, body_y0, width - margin_x, body_y1)

        # Split extract into two halves
        extract = article.get("extract", "")
        words = extract.split()
        mid = len(words) // 2
        text1 = " ".join(words[:mid])
        text2 = " ".join(words[mid:])

        page.insert_textbox(r_col1, text1, fontsize=20, fontname="times-roman", lineheight=1.35)
        page.insert_textbox(r_col2, text2, fontsize=20, fontname="times-roman", lineheight=1.35)

        # Vertical rule between columns
        mid_x = margin_x + col_w + col_gap / 2
        page.draw_line((mid_x, body_y0), (mid_x, body_y1), width=0.5, color=(0.7, 0.7, 0.7))

        return int(body_y1 + 40)

    @classmethod
    def _render_on_this_day(
        cls,
        page: pymupdf.Page,
        events: list[str],
        y_top: int,
        width: int,
        height: int,
    ) -> None:
        """Render historical milestones on Page 1."""
        margin_x = 90
        if y_top > height - 380:
            return

        page.draw_line((margin_x, y_top), (width - margin_x, y_top), width=1.5, color=(0, 0, 0))
        page.insert_text(
            (margin_x, y_top + 30),
            "ON THIS DAY IN HISTORY",
            fontsize=18,
            fontname="helv",
            color=(0.2, 0.2, 0.2),
        )

        cur_y = y_top + 55
        for ev in events[:4]:
            if cur_y > height - 120:
                break
            r = pymupdf.Rect(margin_x, cur_y, width - margin_x, cur_y + 65)
            page.insert_textbox(r, f"•  {ev}", fontsize=17, fontname="times-roman", lineheight=1.3)
            cur_y += 70

    @classmethod
    def _render_feed_pages(
        cls,
        doc: pymupdf.Document,
        articles: list[dict[str, str]],
        date: datetime.date,
        width: int,
        height: int,
    ) -> None:
        """Render RSS news feed articles into 2-column newspaper pages."""
        margin_x = 90
        content_w = width - 2 * margin_x
        col_gap = 50
        col_w = (content_w - col_gap) / 2
        top_y = 170
        bottom_y = height - 120

        col_x0 = [margin_x, margin_x + col_w + col_gap]
        col_x1 = [margin_x + col_w, width - margin_x]

        cur_page = doc.new_page(width=width, height=height)
        cls._render_page_header(cur_page, date, width)

        cur_col = 0
        cur_y = top_y

        for art in articles:
            source = art.get("source", "NEWS").upper()
            title = art.get("title", "")
            summary = art.get("summary", "")

            # Estimate height needed
            needed_h = 140 if len(summary) > 100 else 90

            if cur_y + needed_h > bottom_y:
                # Switch column or page
                if cur_col == 0:
                    cur_col = 1
                    cur_y = top_y
                else:
                    cur_page = doc.new_page(width=width, height=height)
                    cls._render_page_header(cur_page, date, width)
                    cur_col = 0
                    cur_y = top_y

            # Render article in current column
            x0 = col_x0[cur_col]
            x1 = col_x1[cur_col]

            # Source badge
            cur_page.insert_text((x0, cur_y + 16), f"[{source}]", fontsize=13, fontname="helv", color=(0.4, 0.4, 0.4))
            cur_y += 24

            # Title
            r_title = pymupdf.Rect(x0, cur_y, x1, cur_y + 60)
            cur_page.insert_textbox(r_title, title, fontsize=21, fontname="times-bold", color=(0, 0, 0))
            cur_y += 65

            # Summary
            if summary:
                r_desc = pymupdf.Rect(x0, cur_y, x1, cur_y + 85)
                cur_page.insert_textbox(r_desc, summary, fontsize=16, fontname="times-roman", lineheight=1.3)
                cur_y += 90

            # Divider line between articles
            cur_page.draw_line((x0, cur_y + 10), (x1, cur_y + 10), width=0.5, color=(0.8, 0.8, 0.8))
            cur_y += 25

            # Draw vertical line between columns on current page
            mid_x = margin_x + col_w + col_gap / 2
            cur_page.draw_line((mid_x, top_y), (mid_x, bottom_y), width=0.5, color=(0.7, 0.7, 0.7))

    @classmethod
    def _render_page_header(cls, page: pymupdf.Page, date: datetime.date, width: int) -> None:
        """Top running header for inner newspaper pages."""
        margin_x = 90
        header_text = f"THE MORNING CHRONICLE   •   {date.strftime('%A, %B %d, %Y').upper()}   •   WORLD & TECH DISPATCHES"
        page.insert_text((margin_x, 100), header_text, fontsize=15, fontname="helv", color=(0.3, 0.3, 0.3))
        page.draw_line((margin_x, 120), (width - margin_x, 120), width=1.5, color=(0, 0, 0))

    @classmethod
    def _render_footer(cls, page: pymupdf.Page, page_num: int, width: int, height: int, total_pages: int = 1) -> None:
        """Bottom running footer."""
        margin_x = 90
        footer_y = height - 60
        page.draw_line((margin_x, footer_y - 20), (width - margin_x, footer_y - 20), width=0.8, color=(0.6, 0.6, 0.6))
        page.insert_text(
            (margin_x, footer_y),
            "Curated & delivered by Un-remarkable",
            fontsize=14,
            fontname="helv",
            color=(0.4, 0.4, 0.4),
        )
        total_str = f" of {total_pages}" if total_pages > 1 else ""
        page.insert_text(
            (width - margin_x - 120, footer_y),
            f"Page {page_num}{total_str}",
            fontsize=14,
            fontname="helv",
            color=(0.4, 0.4, 0.4),
        )
