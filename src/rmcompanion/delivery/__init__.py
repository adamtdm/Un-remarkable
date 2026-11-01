"""Automated daily newspapers, RSS digests, and crosswords delivery for reMarkable."""

from rmcompanion.delivery.manager import DeliveryManager
from rmcompanion.delivery.models import DeliverySettings
from rmcompanion.delivery.newspaper import DailyNewspaperGenerator
from rmcompanion.delivery.puzzles import DailyPuzzlesGenerator

__all__ = [
    "DailyNewspaperGenerator",
    "DailyPuzzlesGenerator",
    "DeliveryManager",
    "DeliverySettings",
]
