"""Full-text article extractor for RSS feeds, cleaning web pages for e-ink reading."""

from __future__ import annotations

import html
import logging
import re
from html.parser import HTMLParser
from typing import Any

import httpx

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 (Un-remarkable E-Ink Reader)"
)

# Common boilerplate phrases to filter out from article bodies
BOILERPLATE_PATTERNS = [
    re.compile(r"^(?:sign up|subscribe|newsletter|follow us|join our|download the app|read more:)", re.IGNORECASE),
    re.compile(r"^(?:cookies policy|privacy policy|terms of service|all rights reserved|©\s*\d{4})", re.IGNORECASE),
    re.compile(r"^(?:share this story|share on twitter|share on facebook|comment on this)", re.IGNORECASE),
    re.compile(r"^(?:advertisement|sponsored content|promoted stories)", re.IGNORECASE),
]


class ArticleHTMLParser(HTMLParser):
    """Extracts clean article paragraphs and subheadings from web page HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.skip_tags = {
            "script", "style", "nav", "header", "footer", "aside",
            "form", "noscript", "svg", "iframe", "button", "dialog"
        }
        self.current_skip_depth = 0
        self.in_article_depth = 0
        self.article_tag_depth = 0
        self.current_block_tag: str | None = None
        self.current_block_text: list[str] = []
        self.extracted_items: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        attr_dict = {k.lower(): (v or "") for k, v in attrs}

        # Check skip tags
        if tag_lower in self.skip_tags:
            self.current_skip_depth += 1
            return
        if self.current_skip_depth > 0:
            return

        # Check for class or id with ad / sidebar / nav / modal / cookie
        class_id = (attr_dict.get("class", "") + " " + attr_dict.get("id", "")).lower()
        if any(skip_word in class_id for skip_word in ("sidebar", "comment", "related-posts", "cookie-banner", "newsletter-signup", "advert")):
            self.current_skip_depth += 1
            return

        # Check if entering article or main tag
        if tag_lower in ("article", "main") or attr_dict.get("role") == "main" or "articlebody" in attr_dict.get("itemprop", "").lower():
            self.in_article_depth += 1

        # Check for paragraph, headings, blockquotes
        if tag_lower in ("p", "h2", "h3", "blockquote"):
            self.current_block_tag = tag_lower
            self.current_block_text = []

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()

        if self.current_skip_depth > 0:
            if tag_lower in self.skip_tags:
                self.current_skip_depth = max(0, self.current_skip_depth - 1)
            return

        if tag_lower in ("article", "main"):
            self.in_article_depth = max(0, self.in_article_depth - 1)

        if tag_lower in ("p", "h2", "h3", "blockquote") and self.current_block_text:
            raw = "".join(self.current_block_text)
            clean = " ".join(html.unescape(raw).split())

            # Filter trivial strings or boilerplate
            if len(clean) >= 25 and not any(p.search(clean) for p in BOILERPLATE_PATTERNS):
                item_type = "h2" if tag_lower in ("h2", "h3") else ("quote" if tag_lower == "blockquote" else "p")
                self.extracted_items.append({"type": item_type, "text": clean})

            self.current_block_tag = None
            self.current_block_text = []

    def handle_data(self, data: str) -> None:
        if self.current_skip_depth == 0 and self.current_block_tag:
            self.current_block_text.append(data)


async def extract_article_content(
    client: httpx.AsyncClient,
    url: str,
    rss_title: str = "",
    rss_summary: str = "",
    content_encoded: str = "",
    source: str = "",
    category: str = "General",
) -> dict[str, Any]:
    """Extract full article text from a URL or content:encoded with fallback to summary."""
    clean_title = rss_title.strip() or "News Dispatch"
    clean_summary = " ".join(html.unescape(rss_summary).split()) if rss_summary else ""

    # 1. First check if content_encoded provides rich full text (> 180 words)
    if content_encoded and len(content_encoded.split()) > 180:
        parser = ArticleHTMLParser()
        try:
            parser.feed(content_encoded)
            if parser.extracted_items and len(parser.extracted_items) >= 2:
                paragraphs = parser.extracted_items
                total_words = sum(len(p["text"].split()) for p in paragraphs)
                reading_time = max(1, round(total_words / 200))
                return {
                    "title": clean_title,
                    "source": source,
                    "category": category,
                    "url": url,
                    "reading_time_min": reading_time,
                    "word_count": total_words,
                    "paragraphs": paragraphs,
                    "is_full_text": True,
                }
        except Exception as e:
            logger.debug("Error parsing content:encoded for %s: %s", url, e)

    # 2. Fetch live web page HTML
    if url and url.startswith(("http://", "https://")):
        try:
            headers = {"User-Agent": USER_AGENT}
            resp = await client.get(url, headers=headers, timeout=6.5, follow_redirects=True)
            if resp.status_code == 200:
                parser = ArticleHTMLParser()
                parser.feed(resp.text)
                items = parser.extracted_items

                # If enough content extracted (> 25 words total and at least 1 item)
                total_words = sum(len(p["text"].split()) for p in items)
                if total_words >= 25 and len(items) >= 1:
                    reading_time = max(1, round(total_words / 200))
                    return {
                        "title": clean_title,
                        "source": source,
                        "category": category,
                        "url": url,
                        "reading_time_min": reading_time,
                        "word_count": total_words,
                        "paragraphs": items,
                        "is_full_text": True,
                    }
        except Exception as e:
            logger.debug("Failed web article fetch for %s: %s", url, e)

    # 3. Fallback: Use RSS Summary / Teaser
    fallback_text = clean_summary or clean_title
    words = len(fallback_text.split())
    reading_time = max(1, round(words / 200))
    return {
        "title": clean_title,
        "source": source,
        "category": category,
        "url": url,
        "reading_time_min": reading_time,
        "word_count": words,
        "paragraphs": [
            {"type": "p", "text": fallback_text},
            {"type": "note", "text": "[Brief dispatch from RSS summary]"}
        ],
        "is_full_text": False,
    }
