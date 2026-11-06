"""Curated daily newspaper and RSS digest generator with full-text article extraction and interactive navigation."""

from __future__ import annotations

import asyncio
import datetime
import html
import logging
import re
import xml.etree.ElementTree as ET
from typing import Any

import httpx
import pymupdf

from rmcompanion.delivery.article_extractor import extract_article_content
from rmcompanion.delivery.rss_directory import POPULAR_FEEDS

logger = logging.getLogger(__name__)

CATEGORY_MAP = {
    "News": "World & National News",
    "Tech": "Technology & Computing",
    "Science": "Science & Space Exploration",
    "Business": "Business & Finance",
    "Culture": "Culture & Longform Essays",
    "Sports": "Sports & Competition",
}

SECTIONS_ORDER = [
    "World & National News",
    "Technology & Computing",
    "Science & Space Exploration",
    "Business & Finance",
    "Culture & Longform Essays",
    "Sports & Competition",
    "General Dispatches",
]


def clean_html(raw_html: str) -> str:
    """Strip HTML tags and unescape entities for clean plain text."""
    if not raw_html:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = html.unescape(text)
    return " ".join(text.split())


def resolve_feed_category(feed_url: str, channel_title: str) -> str:
    """Match a feed URL or channel title to a clean editorial section."""
    url_lower = feed_url.lower()
    title_lower = channel_title.lower()

    # 1. Match against curated POPULAR_FEEDS
    for f in POPULAR_FEEDS:
        if f["url"].lower() == url_lower or f.get("site_url", "").lower() in url_lower:
            return CATEGORY_MAP.get(f.get("category", ""), "World & National News")

    # 2. Keyword heuristics
    combined = url_lower + " " + title_lower
    if any(k in combined for k in ("tech", "verge", "ars", "wired", "hacker", "lobste", "code", "cyber", "software")):
        return "Technology & Computing"
    if any(k in combined for k in ("science", "nature", "nasa", "space", "quantum", "phys", "astronomy")):
        return "Science & Space Exploration"
    if any(k in combined for k in ("economist", "market", "finance", "wsj", "cnbc", "money", "invest")):
        return "Business & Finance"
    if any(k in combined for k in ("sport", "athletic", "espn", "football", "soccer", "nba", "cricket")):
        return "Sports & Competition"
    if any(k in combined for k in ("culture", "essay", "atlantic", "book", "art", "aeon", "philosophy")):
        return "Culture & Longform Essays"

    return "World & National News"


class DailyNewspaperGenerator:
    """Assembles a multi-column e-ink daily newspaper with interactive Table of Contents and full articles."""

    @classmethod
    async def generate_digest(
        cls,
        rss_feeds: list[str],
        include_wikipedia: bool = True,
        include_weather: bool = True,
        weather_location: str = "London",
        device: str = "paper_pro",  # 'paper_pro' (1620x2160) or 'rm2' (1404x1872)
        target_date: datetime.date | None = None,
        articles_per_feed: int = 2,
        full_body: bool = True,
    ) -> tuple[bytes, str]:
        """Fetch news feeds, Wikipedia, and weather to build the daily newspaper PDF."""
        date = target_date or datetime.date.today()
        width = 1620 if device == "paper_pro" else 1404
        height = 2160 if device == "paper_pro" else 1872

        # 1. Fetch content concurrently
        weather_str = ""
        if include_weather:
            weather_str = await cls._fetch_weather(weather_location)

        wiki_article: dict[str, Any] | None = None
        if include_wikipedia:
            wiki_article, _ = await cls._fetch_wikipedia(date)

        # 2. Fetch RSS items and full article text concurrently
        raw_items = await cls._fetch_all_feeds(rss_feeds, articles_per_feed=articles_per_feed)

        articles: list[dict[str, Any]] = []
        if raw_items:
            if full_body:
                articles = await cls._fetch_full_articles(raw_items)
            else:
                for it in raw_items:
                    words = len((it.get("summary") or "").split())
                    articles.append({
                        "title": it["title"],
                        "source": it["source"],
                        "category": it["category"],
                        "url": it["link"],
                        "reading_time_min": max(1, round(words / 200)),
                        "word_count": words,
                        "paragraphs": [{"type": "p", "text": it.get("summary") or it["title"]}],
                        "is_full_text": False,
                    })

        # 3. Group articles by section
        sections: dict[str, list[dict[str, Any]]] = {}
        for sec in SECTIONS_ORDER:
            sec_arts = [a for a in articles if a.get("category") == sec]
            if sec_arts:
                sections[sec] = sec_arts

        # Any uncategorized articles
        categorized_urls = {a["url"] for sec_arts in sections.values() for a in sec_arts}
        other_arts = [a for a in articles if a["url"] not in categorized_urls]
        if other_arts:
            sections["General Dispatches"] = other_arts

        # 4. Render Article Pages first into article_doc to determine exact target page numbers
        article_doc = pymupdf.open()
        back_link_rects: list[tuple[int, pymupdf.Rect]] = []
        toc_entries: list[dict[str, Any]] = []

        if sections:
            cls._render_article_pages(
                article_doc=article_doc,
                sections=sections,
                back_link_rects=back_link_rects,
                toc_entries=toc_entries,
                width=width,
                height=height,
            )

        # 5. Render Front Page (Page 1) with Masthead, Wikipedia lead, and Executive Table of Contents
        front_doc = pymupdf.open()
        p0 = front_doc.new_page(width=width, height=height)
        cls._render_masthead(p0, date, weather_str, width)

        y_cursor = 245
        if wiki_article:
            y_cursor = cls._render_lead_story(p0, wiki_article, y_cursor, width, height)

        toc_link_rects: list[tuple[pymupdf.Rect, int]] = []
        cls._render_executive_toc(
            page=p0,
            toc_entries=toc_entries,
            toc_link_rects=toc_link_rects,
            y_top=y_cursor,
            width=width,
            height=height,
        )

        # 6. Combine front_doc + article_doc
        if len(article_doc) > 0:
            front_doc.insert_pdf(article_doc)

        total_pages = len(front_doc)

        # 7. Reopen from bytes to enable active PDF internal hyperlinks
        final_doc = pymupdf.open("pdf", front_doc.tobytes())

        # Insert TOC jump links on Page 0 (Page 1)
        for r, target_page_idx in toc_link_rects:
            try:
                final_doc[0].insert_link({"kind": pymupdf.LINK_GOTO, "page": target_page_idx, "from": r})
            except Exception as e:
                logger.debug("Failed adding TOC link: %s", e)

        # Insert Back to TOC links on article pages
        for page_idx, r in back_link_rects:
            try:
                # In final_doc, article_doc page X is at page X + 1
                final_doc[page_idx + 1].insert_link({"kind": pymupdf.LINK_GOTO, "page": 0, "from": r})
            except Exception as e:
                logger.debug("Failed adding back link: %s", e)

        # 8. Render running footer on every page
        for idx, page in enumerate(final_doc):
            cls._render_footer(page, idx + 1, width, height, total_pages=total_pages)

        filename = f"Morning_Chronicle_{date.strftime('%Y-%m-%d')}.pdf"
        return final_doc.tobytes(), filename

    @classmethod
    async def _fetch_weather(cls, location: str = "") -> str:
        """Fetch current weather string from wttr.in (auto-detects by IP if blank)."""
        try:
            loc = location.strip().replace(" ", "+") if location else ""
            url = f"https://wttr.in/{loc}?format=j1" if loc else "https://wttr.in/?format=j1"
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    curr = data["current_condition"][0]
                    temp = curr.get("temp_C", "")
                    desc = curr["weatherDesc"][0].get("value", "")
                    nearest = data.get("nearest_area", [{}])[0].get("areaName", [{}])[0].get("value", "")
                    label = location.strip() if location.strip() else nearest
                    return f"{label}: {temp}°C, {desc}" if label else f"{temp}°C, {desc}"
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
    async def _fetch_single_feed(
        cls, client: httpx.AsyncClient, feed_url: str, limit: int = 2
    ) -> list[dict[str, Any]]:
        """Fetch and parse top article items from a single RSS/Atom feed."""
        url = feed_url.strip()
        if not url:
            return []
        items_out: list[dict[str, Any]] = []
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                root = ET.fromstring(resp.content)
                source_name = "News Dispatch"
                channel = root.find("channel")
                if channel is not None and channel.find("title") is not None and channel.find("title").text:
                    source_name = clean_html(channel.find("title").text)
                elif root.find("{http://www.w3.org/2005/Atom}title") is not None:
                    t_el = root.find("{http://www.w3.org/2005/Atom}title")
                    if t_el.text:
                        source_name = clean_html(t_el.text)

                category = resolve_feed_category(feed_url, source_name)

                items = root.findall(".//item")
                if not items:
                    items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

                for item in items[:limit]:
                    title_el = item.find("title") if item.find("title") is not None else item.find("{http://www.w3.org/2005/Atom}title")
                    desc_el = (
                        item.find("description")
                        if item.find("description") is not None
                        else item.find("{http://www.w3.org/2005/Atom}summary")
                    )
                    link_el = item.find("link") if item.find("link") is not None else item.find("{http://www.w3.org/2005/Atom}link")
                    encoded_el = item.find("{http://purl.org/rss/1.0/modules/content/}encoded")

                    title = clean_html(title_el.text if title_el is not None and title_el.text else "")
                    desc = clean_html(desc_el.text if desc_el is not None and desc_el.text else "")
                    link = ""
                    if link_el is not None:
                        link = link_el.text or link_el.attrib.get("href", "")
                    content_encoded = encoded_el.text if encoded_el is not None and encoded_el.text else ""

                    if title:
                        items_out.append({
                            "source": source_name,
                            "category": category,
                            "title": title,
                            "summary": desc,
                            "link": link.strip(),
                            "content_encoded": content_encoded,
                        })
        except Exception as e:
            logger.warning("Error fetching RSS feed %s: %s", url, e)
        return items_out

    @classmethod
    async def _fetch_all_feeds(cls, feeds: list[str], articles_per_feed: int = 2) -> list[dict[str, Any]]:
        """Fetch items from multiple RSS/Atom feeds concurrently."""
        headers = {"User-Agent": "Un-remarkable/0.1.0 (reMarkable Companion RSS Reader)"}
        async with httpx.AsyncClient(timeout=8.0, headers=headers, follow_redirects=True) as client:
            tasks = [cls._fetch_single_feed(client, f, limit=articles_per_feed) for f in feeds if f.strip()]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        items: list[dict[str, Any]] = []
        for r in results:
            if isinstance(r, list):
                items.extend(r)
        return items

    @classmethod
    async def _fetch_full_articles(cls, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Fetch full article content for all feed items in parallel."""
        async with httpx.AsyncClient(timeout=7.0, follow_redirects=True) as client:
            tasks = [
                extract_article_content(
                    client=client,
                    url=it.get("link", ""),
                    rss_title=it.get("title", ""),
                    rss_summary=it.get("summary", ""),
                    content_encoded=it.get("content_encoded", ""),
                    source=it.get("source", ""),
                    category=it.get("category", "General"),
                )
                for it in items
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        articles: list[dict[str, Any]] = []
        for r, orig_item in zip(results, items):
            if isinstance(r, dict):
                articles.append(r)
            else:
                # Fallback to orig summary
                words = len((orig_item.get("summary") or "").split())
                articles.append({
                    "title": orig_item.get("title", ""),
                    "source": orig_item.get("source", ""),
                    "category": orig_item.get("category", "General"),
                    "url": orig_item.get("link", ""),
                    "reading_time_min": max(1, round(words / 200)),
                    "word_count": words,
                    "paragraphs": [{"type": "p", "text": orig_item.get("summary") or orig_item.get("title", "")}],
                    "is_full_text": False,
                })
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
        """Render a concise Wikipedia Featured Article of the Day on Page 1."""
        margin_x = 90
        content_w = width - 2 * margin_x

        # Category eyebrow
        page.insert_text(
            (margin_x, y_top + 18),
            "TODAY'S FEATURED INSIGHT  •  WIKIPEDIA ESSENTIAL KNOWLEDGE",
            fontsize=13,
            fontname="helv",
            color=(0.35, 0.35, 0.35),
        )

        # Headline
        title = article.get("title", "Featured Article")
        rect_title = pymupdf.Rect(margin_x, y_top + 28, width - margin_x, y_top + 85)
        page.insert_textbox(rect_title, title, fontsize=28, fontname="times-bold", color=(0, 0, 0))

        # Divider under headline
        page.draw_line((margin_x, y_top + 92), (width - margin_x, y_top + 92), width=0.6, color=(0.5, 0.5, 0.5))

        # Article extract in 2 balanced columns
        col_gap = 50
        col_w = (content_w - col_gap) / 2
        body_y0 = y_top + 105
        body_y1 = body_y0 + 195

        r_col1 = pymupdf.Rect(margin_x, body_y0, margin_x + col_w, body_y1)
        r_col2 = pymupdf.Rect(margin_x + col_w + col_gap, body_y0, width - margin_x, body_y1)

        extract = article.get("extract", "")
        words = extract.split()
        mid = len(words) // 2
        text1 = " ".join(words[:mid])
        text2 = " ".join(words[mid:])

        page.insert_textbox(r_col1, text1, fontsize=17, fontname="times-roman", lineheight=1.35)
        page.insert_textbox(r_col2, text2, fontsize=17, fontname="times-roman", lineheight=1.35)

        # Vertical rule between columns
        mid_x = margin_x + col_w + col_gap / 2
        page.draw_line((mid_x, body_y0), (mid_x, body_y1), width=0.5, color=(0.75, 0.75, 0.75))

        return int(body_y1 + 25)

    @classmethod
    def _render_executive_toc(
        cls,
        page: pymupdf.Page,
        toc_entries: list[dict[str, Any]],
        toc_link_rects: list[tuple[pymupdf.Rect, int]],
        y_top: int,
        width: int,
        height: int,
    ) -> None:
        """Render the Sectioned Executive Table of Contents with jump link rectangles on Page 1."""
        margin_x = 90
        content_w = width - 2 * margin_x
        bottom_y = height - 90

        # Section banner
        page.draw_line((margin_x, y_top), (width - margin_x, y_top), width=2.0, color=(0, 0, 0))
        page.draw_line((margin_x, y_top + 4), (width - margin_x, y_top + 4), width=0.8, color=(0, 0, 0))

        page.insert_text(
            (margin_x, y_top + 28),
            "TODAY'S SECTIONS & READING COMPASS   •   TAP ANY HEADLINE TO READ",
            fontsize=15,
            fontname="helv",
            color=(0.2, 0.2, 0.2),
        )
        page.draw_line((margin_x, y_top + 40), (width - margin_x, y_top + 40), width=1.0, color=(0, 0, 0))

        if not toc_entries:
            page.insert_text(
                (margin_x, y_top + 80),
                "No feeds configured. Select popular feeds in Settings to deliver daily articles.",
                fontsize=17,
                fontname="times-italic",
                color=(0.4, 0.4, 0.4),
            )
            return

        # Group TOC entries by section
        sections_dict: dict[str, list[dict[str, Any]]] = {}
        for entry in toc_entries:
            sec = entry.get("section", "General")
            sections_dict.setdefault(sec, []).append(entry)

        col_gap = 60
        col_w = (content_w - col_gap) / 2
        cols_x = [
            (margin_x, margin_x + col_w),
            (margin_x + col_w + col_gap, width - margin_x),
        ]

        cur_col = 0
        cur_y = y_top + 65

        for sec_name, entries in sections_dict.items():
            needed_h = 35 + (len(entries) * 58)
            if cur_y + needed_h > bottom_y and cur_col == 0:
                cur_col = 1
                cur_y = y_top + 65

            x0, x1 = cols_x[cur_col]

            # Section Title
            page.insert_text((x0, cur_y + 16), sec_name.upper(), fontsize=15, fontname="times-bold", color=(0, 0, 0))
            page.draw_line((x0, cur_y + 22), (x1, cur_y + 22), width=0.5, color=(0.4, 0.4, 0.4))
            cur_y += 36

            for it in entries:
                if cur_y + 54 > bottom_y and cur_col == 0:
                    cur_col = 1
                    cur_y = y_top + 65
                    x0, x1 = cols_x[cur_col]

                # Bounding box for tapping
                r_entry = pymupdf.Rect(x0, cur_y - 2, x1, cur_y + 50)
                target_page_idx = it["target_page_idx"]
                toc_link_rects.append((r_entry, target_page_idx))

                # Headline
                title = it["title"]
                if len(title) > 65:
                    title = title[:62] + "..."
                page.insert_text(
                    (x0 + 8, cur_y + 15),
                    f"•  [{it['source']}] {title}",
                    fontsize=16,
                    fontname="times-bold",
                    color=(0, 0, 0),
                )

                # Meta line with page number
                page_label = f"Go to Page {it['target_page_num']} →"
                meta_str = f"{it['reading_time_min']} min read   •   {page_label}"
                page.insert_text((x0 + 22, cur_y + 36), meta_str, fontsize=13, fontname="times-italic", color=(0.35, 0.35, 0.35))

                cur_y += 54

            cur_y += 18

    @classmethod
    def _render_article_pages(
        cls,
        article_doc: pymupdf.Document,
        sections: dict[str, list[dict[str, Any]]],
        back_link_rects: list[tuple[int, pymupdf.Rect]],
        toc_entries: list[dict[str, Any]],
        width: int,
        height: int,
    ) -> None:
        """Render dedicated 1-article-per-page layouts grouped by section."""
        margin_x = 90
        content_w = width - 2 * margin_x
        col_gap = 50
        col_w = (content_w - col_gap) / 2
        bottom_y = height - 120

        cols = [
            (margin_x, margin_x + col_w),
            (margin_x + col_w + col_gap, width - margin_x),
        ]

        for sec_name, articles in sections.items():
            for art in articles:
                # Article starts on a fresh page in article_doc
                start_pno = len(article_doc)
                final_page_num = start_pno + 2  # Page 1 is Front Page

                toc_entries.append({
                    "section": sec_name,
                    "title": art["title"],
                    "source": art["source"],
                    "reading_time_min": art.get("reading_time_min", 2),
                    "word_count": art.get("word_count", 0),
                    "target_page_idx": start_pno + 1,  # 0-indexed in final_doc
                    "target_page_num": final_page_num,
                })

                cur_page = article_doc.new_page(width=width, height=height)
                back_rect = pymupdf.Rect(margin_x - 5, 75, margin_x + 195, 110)
                back_link_rects.append((start_pno, back_rect))

                # 1. Top Navigation & Running Header
                cur_page.draw_rect(back_rect, width=0.8, color=(0.5, 0.5, 0.5))
                cur_page.insert_text((margin_x + 8, 97), "← BACK TO INDEX", fontsize=14, fontname="helv", color=(0.2, 0.2, 0.2))

                header_right = f"{sec_name.upper()}   •   {art['source'].upper()}"
                cur_page.insert_text((width - margin_x - 520, 97), header_right, fontsize=13, fontname="helv", color=(0.4, 0.4, 0.4))
                cur_page.draw_line((margin_x, 118), (width - margin_x, 118), width=1.0, color=(0, 0, 0))

                # 2. Headline
                title = art.get("title", "")
                r_title = pymupdf.Rect(margin_x, 145, width - margin_x, 245)
                cur_page.insert_textbox(r_title, title, fontsize=31, fontname="times-bold", lineheight=1.2)

                # 3. Byline
                y_byline = 265
                byline_str = f"Reported by {art['source']}   •   {art.get('reading_time_min', 2)} min read ({art.get('word_count', 0)} words)"
                cur_page.insert_text((margin_x, y_byline), byline_str, fontsize=15, fontname="times-italic", color=(0.35, 0.35, 0.35))
                cur_page.draw_line((margin_x, y_byline + 15), (width - margin_x, y_byline + 15), width=0.8, color=(0.4, 0.4, 0.4))

                # 4. Body Paragraphs across 2 columns
                body_y_start = y_byline + 38
                cur_col = 0
                cur_y = body_y_start

                paragraphs = art.get("paragraphs", [])
                for p_item in paragraphs:
                    p_type = p_item.get("type", "p")
                    text = p_item.get("text", "").strip()
                    if not text:
                        continue

                    fsize = 20 if p_type in ("h2", "h3") else 18
                    fname = "times-bold" if p_type in ("h2", "h3") else ("times-italic" if p_type == "quote" else "times-roman")
                    lheight = 1.25 if p_type in ("h2", "h3") else 1.35

                    # Check if current column has enough vertical room
                    if cur_y + 50 >= bottom_y:
                        if cur_col == 0:
                            cur_col = 1
                            cur_y = body_y_start
                        else:
                            # Continuation Page
                            cont_pno = len(article_doc)
                            cur_page.insert_text(
                                (width - margin_x - 280, bottom_y + 10),
                                "Continued on next page →",
                                fontsize=14,
                                fontname="times-italic",
                                color=(0.4, 0.4, 0.4),
                            )
                            cur_page = article_doc.new_page(width=width, height=height)
                            back_rect_cont = pymupdf.Rect(margin_x - 5, 75, margin_x + 195, 110)
                            back_link_rects.append((cont_pno, back_rect_cont))

                            cur_page.draw_rect(back_rect_cont, width=0.8, color=(0.5, 0.5, 0.5))
                            cur_page.insert_text((margin_x + 8, 97), "← BACK TO INDEX", fontsize=14, fontname="helv", color=(0.2, 0.2, 0.2))

                            cont_header = f"{sec_name.upper()}   •   {title[:35]} (CONT.)"
                            cur_page.insert_text((width - margin_x - 520, 97), cont_header, fontsize=13, fontname="helv", color=(0.4, 0.4, 0.4))
                            cur_page.draw_line((margin_x, 118), (width - margin_x, 118), width=1.0, color=(0, 0, 0))

                            cur_col = 0
                            cur_y = 150
                            body_y_start = 150

                    x0, x1 = cols[cur_col]
                    rect = pymupdf.Rect(x0, cur_y, x1, max(cur_y + 50, bottom_y))
                    rc = cur_page.insert_textbox(rect, text, fontsize=fsize, fontname=fname, lineheight=lheight)

                    if rc >= 0:
                        cur_y += (rect.height - rc) + (22 if p_type in ("h2", "h3") else 18)
                    else:
                        # Switch column or page
                        if cur_col == 0:
                            cur_col = 1
                            cur_y = body_y_start
                        else:
                            # Add continuation marker
                            cur_page.insert_text(
                                (width - margin_x - 280, bottom_y + 10),
                                "Continued on next page →",
                                fontsize=14,
                                fontname="times-italic",
                                color=(0.4, 0.4, 0.4),
                            )

                            # Create Continuation Page
                            cont_pno = len(article_doc)
                            cur_page = article_doc.new_page(width=width, height=height)
                            back_rect_cont = pymupdf.Rect(margin_x - 5, 75, margin_x + 195, 110)
                            back_link_rects.append((cont_pno, back_rect_cont))

                            cur_page.draw_rect(back_rect_cont, width=0.8, color=(0.5, 0.5, 0.5))
                            cur_page.insert_text((margin_x + 8, 97), "← BACK TO INDEX", fontsize=14, fontname="helv", color=(0.2, 0.2, 0.2))

                            cont_header = f"{sec_name.upper()}   •   {title[:35]} (CONT.)"
                            cur_page.insert_text((width - margin_x - 520, 97), cont_header, fontsize=13, fontname="helv", color=(0.4, 0.4, 0.4))
                            cur_page.draw_line((margin_x, 118), (width - margin_x, 118), width=1.0, color=(0, 0, 0))

                            cur_col = 0
                            cur_y = 150
                            body_y_start = 150

                        x0, x1 = cols[cur_col]
                        rect = pymupdf.Rect(x0, cur_y, x1, max(cur_y + 50, bottom_y))
                        rc = cur_page.insert_textbox(rect, text, fontsize=fsize, fontname=fname, lineheight=lheight)
                        if rc >= 0:
                            cur_y += (rect.height - rc) + (22 if p_type in ("h2", "h3") else 18)
                        else:
                            cur_y = bottom_y

    @classmethod
    def _render_footer(
        cls,
        page: pymupdf.Page,
        page_num: int,
        width: int,
        height: int,
        total_pages: int = 1,
    ) -> None:
        """Bottom running footer."""
        margin_x = 90
        footer_y = height - 55
        page.draw_line((margin_x, footer_y - 18), (width - margin_x, footer_y - 18), width=0.8, color=(0.6, 0.6, 0.6))
        page.insert_text(
            (margin_x, footer_y),
            "Curated & delivered by Un-remarkable",
            fontsize=14,
            fontname="helv",
            color=(0.4, 0.4, 0.4),
        )
        total_str = f" of {total_pages}" if total_pages > 1 else ""
        page.insert_text(
            (width - margin_x - 140, footer_y),
            f"Page {page_num}{total_str}",
            fontsize=14,
            fontname="helv",
            color=(0.4, 0.4, 0.4),
        )
