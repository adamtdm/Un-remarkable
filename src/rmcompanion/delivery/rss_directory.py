"""Curated RSS feeds directory, presets, auto-discovery, and validation for reMarkable daily newspapers."""

from __future__ import annotations

import html
import logging
import re
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Standard user-agent for RSS requests
RSS_USER_AGENT = "Un-remarkable/0.1.0 (reMarkable Daily Newspaper RSS Reader; +https://github.com/)"

CATEGORIES = ["All", "News", "Tech", "Science", "Business", "Culture", "Sports"]

POPULAR_FEEDS: list[dict[str, Any]] = [
    # --- General & World News ---
    {
        "id": "bbc-news",
        "name": "BBC News (Top Stories)",
        "url": "https://feeds.bbci.co.uk/news/rss.xml",
        "site_url": "https://www.bbc.com/news",
        "category": "News",
        "description": "Top international and UK headlines from the BBC.",
        "is_default": True,
    },
    {
        "id": "bbc-world",
        "name": "BBC World News",
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "site_url": "https://www.bbc.com/news/world",
        "category": "News",
        "description": "Global breaking news and international affairs from the BBC.",
        "is_default": False,
    },
    {
        "id": "guardian-world",
        "name": "The Guardian (World)",
        "url": "https://www.theguardian.com/world/rss",
        "site_url": "https://www.theguardian.com",
        "category": "News",
        "description": "Independent international journalism from The Guardian.",
        "is_default": True,
    },
    {
        "id": "npr-news",
        "name": "NPR News (Top Stories)",
        "url": "https://feeds.npr.org/1001/rss.xml",
        "site_url": "https://www.npr.org",
        "category": "News",
        "description": "National Public Radio top stories, investigative reporting, and analysis.",
        "is_default": True,
    },
    {
        "id": "nyt-world",
        "name": "The New York Times (World)",
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        "site_url": "https://www.nytimes.com",
        "category": "News",
        "description": "World news and international coverage from The New York Times.",
        "is_default": False,
    },
    {
        "id": "aljazeera-english",
        "name": "Al Jazeera English",
        "url": "https://www.aljazeera.com/xml/rss/all.xml",
        "site_url": "https://www.aljazeera.com",
        "category": "News",
        "description": "In-depth international reporting from Al Jazeera.",
        "is_default": False,
    },
    {
        "id": "dw-news",
        "name": "Deutsche Welle (DW)",
        "url": "https://rss.dw.com/rdf/rss-en-all",
        "site_url": "https://www.dw.com",
        "category": "News",
        "description": "International news and analysis from Germany's public broadcaster.",
        "is_default": False,
    },
    {
        "id": "pbs-newshour",
        "name": "PBS NewsHour",
        "url": "https://www.pbs.org/newshour/feeds/rss/headlines",
        "site_url": "https://www.pbs.org/newshour",
        "category": "News",
        "description": "Thoughtful, in-depth evening news from public television.",
        "is_default": False,
    },

    # --- Technology & Programming ---
    {
        "id": "hacker-news",
        "name": "Hacker News",
        "url": "https://news.ycombinator.com/rss",
        "site_url": "https://news.ycombinator.com",
        "category": "Tech",
        "description": "Top tech, programming, and startup links curated by the community.",
        "is_default": True,
    },
    {
        "id": "the-verge",
        "name": "The Verge",
        "url": "https://www.theverge.com/rss/index.xml",
        "site_url": "https://www.theverge.com",
        "category": "Tech",
        "description": "Technology, science, art, and culture reporting.",
        "is_default": True,
    },
    {
        "id": "ars-technica",
        "name": "Ars Technica",
        "url": "https://feeds.arstechnica.com/arstechnica/index",
        "site_url": "https://arstechnica.com",
        "category": "Tech",
        "description": "Deep analysis of technology, software, science, and policy.",
        "is_default": True,
    },
    {
        "id": "wired-top",
        "name": "WIRED (Top Stories)",
        "url": "https://www.wired.com/feed/rss",
        "site_url": "https://www.wired.com",
        "category": "Tech",
        "description": "How emerging technologies affect culture, the economy, and politics.",
        "is_default": False,
    },
    {
        "id": "lobsters",
        "name": "Lobste.rs",
        "url": "https://lobste.rs/rss",
        "site_url": "https://lobste.rs",
        "category": "Tech",
        "description": "Computing-focused discussion community and links.",
        "is_default": False,
    },
    {
        "id": "techcrunch",
        "name": "TechCrunch",
        "url": "https://techcrunch.com/feed/",
        "site_url": "https://techcrunch.com",
        "category": "Tech",
        "description": "Startup news, technology trends, and venture capital.",
        "is_default": False,
    },
    {
        "id": "mit-tech-review",
        "name": "MIT Technology Review",
        "url": "https://www.technologyreview.com/feed/",
        "site_url": "https://www.technologyreview.com",
        "category": "Tech",
        "description": "Authoritative reporting on commercial and social impact of tech.",
        "is_default": False,
    },
    {
        "id": "bleeping-computer",
        "name": "BleepingComputer",
        "url": "https://www.bleepingcomputer.com/feed/",
        "site_url": "https://www.bleepingcomputer.com",
        "category": "Tech",
        "description": "Information security, ransomware, and cybersecurity news.",
        "is_default": False,
    },

    # --- Science & Space ---
    {
        "id": "nature-news",
        "name": "Nature News",
        "url": "https://www.nature.com/nature.rss",
        "site_url": "https://www.nature.com",
        "category": "Science",
        "description": "Latest peer-reviewed science news, discoveries, and breakthroughs.",
        "is_default": True,
    },
    {
        "id": "nasa-breaking",
        "name": "NASA Breaking News",
        "url": "https://www.nasa.gov/news-release/feed/",
        "site_url": "https://www.nasa.gov",
        "category": "Science",
        "description": "Space exploration, astronomy, planetary discoveries, and missions.",
        "is_default": False,
    },
    {
        "id": "quanta-magazine",
        "name": "Quanta Magazine",
        "url": "https://www.quantamagazine.org/feed/",
        "site_url": "https://www.quantamagazine.org",
        "category": "Science",
        "description": "Illuminating physics, mathematics, biology, and computer science.",
        "is_default": False,
    },
    {
        "id": "phys-org",
        "name": "Phys.org",
        "url": "https://phys.org/rss-feed/",
        "site_url": "https://phys.org",
        "category": "Science",
        "description": "Physics, nanotechnology, astronomy, and earth science news.",
        "is_default": False,
    },
    {
        "id": "sciam-news",
        "name": "Scientific American",
        "url": "https://www.scientificamerican.com/rss/news/",
        "site_url": "https://www.scientificamerican.com",
        "category": "Science",
        "description": "Expert perspectives on science, health, technology, and the environment.",
        "is_default": False,
    },

    # --- Business & Markets ---
    {
        "id": "economist-finance",
        "name": "The Economist (Finance & Economics)",
        "url": "https://www.economist.com/finance-and-economics/rss.xml",
        "site_url": "https://www.economist.com",
        "category": "Business",
        "description": "Global economics, markets, and monetary policy analysis.",
        "is_default": False,
    },
    {
        "id": "cnbc-top",
        "name": "CNBC (Top News)",
        "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "site_url": "https://www.cnbc.com",
        "category": "Business",
        "description": "Stock markets, earnings, finance, and company headlines.",
        "is_default": False,
    },
    {
        "id": "wsj-world",
        "name": "Wall Street Journal (World)",
        "url": "https://feeds.a.dj.com/rss/RSSWorldNews.xml",
        "site_url": "https://www.wsj.com",
        "category": "Business",
        "description": "Business, international economics, and trade reporting.",
        "is_default": False,
    },
    {
        "id": "marketwatch-top",
        "name": "MarketWatch (Top Stories)",
        "url": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
        "site_url": "https://www.marketwatch.com",
        "category": "Business",
        "description": "Financial market movements, stock analysis, and personal finance.",
        "is_default": False,
    },

    # --- Culture, Longform & Thought ---
    {
        "id": "aeon-essays",
        "name": "Aeon Essays",
        "url": "https://aeon.co/feed.rss",
        "site_url": "https://aeon.co",
        "category": "Culture",
        "description": "Deep philosophical essays, ideas, and cultural perspectives.",
        "is_default": False,
    },
    {
        "id": "the-atlantic",
        "name": "The Atlantic",
        "url": "https://www.theatlantic.com/feed/all/",
        "site_url": "https://www.theatlantic.com",
        "category": "Culture",
        "description": "Longform journalism on politics, culture, and society.",
        "is_default": False,
    },
    {
        "id": "conversation-global",
        "name": "The Conversation",
        "url": "https://theconversation.com/global/articles.atom",
        "site_url": "https://theconversation.com",
        "category": "Culture",
        "description": "Academic rigor and journalistic flair from researchers worldwide.",
        "is_default": False,
    },
    {
        "id": "kottke-org",
        "name": "kottke.org",
        "url": "https://feeds.kottke.org/main",
        "site_url": "https://kottke.org",
        "category": "Culture",
        "description": "One of the web's oldest blogs covering art, science, design, and history.",
        "is_default": False,
    },

    # --- Sports ---
    {
        "id": "bbc-sport",
        "name": "BBC Sport",
        "url": "https://feeds.bbci.co.uk/sport/rss.xml",
        "site_url": "https://www.bbc.com/sport",
        "category": "Sports",
        "description": "Scores, match reports, and global sporting news.",
        "is_default": False,
    },
    {
        "id": "guardian-sport",
        "name": "The Guardian (Sport)",
        "url": "https://www.theguardian.com/sport/rss",
        "site_url": "https://www.theguardian.com/sport",
        "category": "Sports",
        "description": "Comprehensive sports journalism, live reports, and commentary.",
        "is_default": False,
    },
]

PRESETS: list[dict[str, Any]] = [
    {
        "id": "balanced",
        "name": "Editor's Choice (Balanced)",
        "description": "Well-rounded daily morning edition: world news, tech, science, and public radio.",
        "feeds": [
            "https://feeds.bbci.co.uk/news/rss.xml",
            "https://www.theguardian.com/world/rss",
            "https://feeds.npr.org/1001/rss.xml",
            "https://news.ycombinator.com/rss",
            "https://www.theverge.com/rss/index.xml",
            "https://feeds.arstechnica.com/arstechnica/index",
            "https://www.nature.com/nature.rss",
        ],
    },
    {
        "id": "world-news",
        "name": "Global & World News",
        "description": "In-depth international dispatches and world headlines.",
        "feeds": [
            "https://feeds.bbci.co.uk/news/rss.xml",
            "https://feeds.bbci.co.uk/news/world/rss.xml",
            "https://www.theguardian.com/world/rss",
            "https://feeds.npr.org/1001/rss.xml",
            "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
            "https://www.aljazeera.com/xml/rss/all.xml",
        ],
    },
    {
        "id": "tech-dev",
        "name": "Tech & Developer Brief",
        "description": "Hardware, software, open source, and Silicon Valley developments.",
        "feeds": [
            "https://news.ycombinator.com/rss",
            "https://www.theverge.com/rss/index.xml",
            "https://feeds.arstechnica.com/arstechnica/index",
            "https://www.wired.com/feed/rss",
            "https://lobste.rs/rss",
            "https://www.technologyreview.com/feed/",
        ],
    },
    {
        "id": "science-nature",
        "name": "Science & Space Exploration",
        "description": "Scientific discoveries, astronomy missions, and foundational research.",
        "feeds": [
            "https://www.nature.com/nature.rss",
            "https://www.nasa.gov/news-release/feed/",
            "https://www.quantamagazine.org/feed/",
            "https://phys.org/rss-feed/",
            "https://www.scientificamerican.com/rss/news/",
        ],
    },
    {
        "id": "business-markets",
        "name": "Business & Finance",
        "description": "Global markets, monetary policy, and corporate earnings.",
        "feeds": [
            "https://www.economist.com/finance-and-economics/rss.xml",
            "https://www.cnbc.com/id/100003114/device/rss/rss.html",
            "https://feeds.a.dj.com/rss/RSSWorldNews.xml",
            "https://feeds.content.dowjones.io/public/rss/mw_topstories",
        ],
    },
    {
        "id": "longform-ideas",
        "name": "Essays & Deep Reads",
        "description": "Reflective essays, cultural critique, and philosophy.",
        "feeds": [
            "https://aeon.co/feed.rss",
            "https://www.theatlantic.com/feed/all/",
            "https://theconversation.com/global/articles.atom",
            "https://feeds.kottke.org/main",
        ],
    },
]


def clean_text(raw: str) -> str:
    """Strip tags and unescape text."""
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    return " ".join(text.split())


def search_popular_feeds(query: str = "", category: str = "All") -> list[dict[str, Any]]:
    """Filter curated popular feeds by query and category."""
    q = query.strip().lower()
    cat = category.strip().capitalize() if category and category.lower() != "all" else "All"

    results = []
    for f in POPULAR_FEEDS:
        if cat != "All" and f["category"].lower() != cat.lower():
            continue
        if q:
            match = (
                q in f["name"].lower()
                or q in f["description"].lower()
                or q in f["category"].lower()
                or q in f["url"].lower()
                or q in f.get("site_url", "").lower()
            )
            if not match:
                continue
        results.append(f)
    return results


async def validate_feed(feed_url: str) -> dict[str, Any]:
    """Fetch and validate an RSS/Atom feed, extracting title and recent headlines."""
    url = feed_url.strip()
    if not url:
        return {"valid": False, "error": "URL cannot be empty"}

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        headers = {"User-Agent": RSS_USER_AGENT}
        async with httpx.AsyncClient(timeout=7.0, headers=headers, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return {
                    "valid": False,
                    "url": url,
                    "error": f"HTTP status {resp.status_code}",
                }

            root = ET.fromstring(resp.content)
            title = ""
            desc = ""

            # Check RSS channel
            channel = root.find("channel")
            if channel is not None:
                t_el = channel.find("title")
                d_el = channel.find("description")
                if t_el is not None and t_el.text:
                    title = clean_text(t_el.text)
                if d_el is not None and d_el.text:
                    desc = clean_text(d_el.text)

            # Check Atom feed
            if not title:
                t_el = root.find("{http://www.w3.org/2005/Atom}title")
                d_el = root.find("{http://www.w3.org/2005/Atom}subtitle")
                if t_el is not None and t_el.text:
                    title = clean_text(t_el.text)
                if d_el is not None and d_el.text:
                    desc = clean_text(d_el.text)

            # Extract articles
            items = root.findall(".//item")
            if not items:
                items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

            articles = []
            for item in items[:5]:
                art_t = item.find("title") if item.find("title") is not None else item.find("{http://www.w3.org/2005/Atom}title")
                art_l = item.find("link") if item.find("link") is not None else item.find("{http://www.w3.org/2005/Atom}link")
                link_val = ""
                if art_l is not None:
                    link_val = art_l.text or art_l.attrib.get("href", "")
                t_val = clean_text(art_t.text if art_t is not None and art_t.text else "")
                if t_val:
                    articles.append({"title": t_val, "link": link_val})

            return {
                "valid": True,
                "url": url,
                "title": title or "RSS Feed",
                "description": desc,
                "article_count": len(items),
                "articles": articles,
            }
    except Exception as e:
        logger.warning("Error validating feed %s: %s", url, e)
        return {
            "valid": False,
            "url": url,
            "error": str(e),
        }


async def discover_feed_url(target: str) -> list[dict[str, Any]]:
    """Discover RSS or Atom feeds from a given URL or domain name."""
    url = target.strip()
    if not url:
        return []

    # If domain without scheme:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    discovered: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    try:
        headers = {"User-Agent": RSS_USER_AGENT}
        async with httpx.AsyncClient(timeout=7.0, headers=headers, follow_redirects=True) as client:
            resp = await client.get(url)
            try:
                current_url = str(resp.url)
            except (RuntimeError, AttributeError):
                current_url = url

            content_type = resp.headers.get("content-type", "").lower()
            content_start = resp.content[:1500].lower()

            # 1. Direct XML feed
            if (
                "application/rss+xml" in content_type
                or "application/atom+xml" in content_type
                or "text/xml" in content_type
                or b"<rss" in content_start
                or b"<feed" in content_start
            ):
                validation = await validate_feed(current_url)
                if validation.get("valid"):
                    return [{
                        "url": current_url,
                        "title": validation.get("title") or "Direct Feed",
                        "description": validation.get("description") or "",
                        "source": "Direct Feed URL",
                        "article_count": validation.get("article_count", 0),
                        "articles": validation.get("articles", []),
                    }]

            # 2. HTML Auto-discovery via <link rel="alternate">
            html_text = resp.text
            link_pattern = re.compile(
                r'<link[^>]+type=[\"\'](application/(?:rss|atom)\+xml|text/xml)[\"\'][^>]*>',
                re.IGNORECASE,
            )
            for tag in link_pattern.finditer(html_text):
                tag_str = tag.group(0)
                href_m = re.search(r'href=[\"\']([^\s\"\'>]+)[\"\']', tag_str, re.IGNORECASE)
                title_m = re.search(r'title=[\"\']([^\s\"\'>]+)[\"\']', tag_str, re.IGNORECASE)
                if href_m:
                    feed_url = urllib.parse.urljoin(current_url, href_m.group(1))
                    if feed_url not in seen_urls:
                        seen_urls.add(feed_url)
                        discovered.append({
                            "url": feed_url,
                            "title": title_m.group(1) if title_m else "",
                            "source": "HTML <link> tag",
                        })

            # 3. Fallback: Check common paths if none discovered in <link>
            if not discovered:
                candidates = ["/feed", "/rss", "/rss.xml", "/atom.xml", "/feed.xml"]
                for path in candidates:
                    test_url = urllib.parse.urljoin(current_url, path)
                    if test_url in seen_urls:
                        continue
                    try:
                        probe = await client.get(test_url)
                        if probe.status_code == 200:
                            p_type = probe.headers.get("content-type", "").lower()
                            p_start = probe.content[:1000].lower()
                            if (
                                "xml" in p_type
                                or b"<rss" in p_start
                                or b"<feed" in p_start
                            ):
                                seen_urls.add(test_url)
                                discovered.append({
                                    "url": test_url,
                                    "title": "",
                                    "source": f"Standard path {path}",
                                })
                                break
                    except Exception:
                        pass

            # Validate each discovered candidate
            verified_results: list[dict[str, Any]] = []
            for item in discovered[:5]:
                val = await validate_feed(item["url"])
                if val.get("valid"):
                    verified_results.append({
                        "url": item["url"],
                        "title": val.get("title") or item["title"] or "Discovered Feed",
                        "description": val.get("description", ""),
                        "source": item.get("source", "Discovered"),
                        "article_count": val.get("article_count", 0),
                        "articles": val.get("articles", []),
                    })

            return verified_results
    except Exception as e:
        logger.warning("Error discovering feeds on %s: %s", target, e)
        return []
