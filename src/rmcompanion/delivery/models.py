"""Data models for automated news and puzzle delivery."""

from __future__ import annotations

from pydantic import BaseModel, Field

DEFAULT_RSS_FEEDS = [
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://news.ycombinator.com/rss",
    "https://www.theverge.com/rss/index.xml",
]


class DeliverySettings(BaseModel):
    """Configuration for automated daily newspapers, RSS digests, and crosswords."""

    # News & RSS Digest
    news_enabled: bool = False
    news_folder: str = "Daily News"
    news_delivery_time: str = "06:00"  # HH:MM
    news_device: str = "paper_pro"  # paper_pro, rm2, rm1
    news_rss_feeds: list[str] = Field(default_factory=lambda: list(DEFAULT_RSS_FEEDS))
    news_include_wikipedia: bool = True
    news_include_weather: bool = True
    news_weather_location: str = "London"

    # Crosswords & Puzzles
    puzzles_enabled: bool = False
    puzzles_folder: str = "Puzzles"
    puzzles_delivery_time: str = "06:00"
    puzzles_guardian_quick: bool = True
    puzzles_guardian_cryptic: bool = True
    puzzles_sudoku: bool = True
    puzzles_sudoku_difficulty: str = "medium"  # easy, medium, hard

    # Tracking
    last_news_delivery: str = ""
    last_puzzles_delivery: str = ""
