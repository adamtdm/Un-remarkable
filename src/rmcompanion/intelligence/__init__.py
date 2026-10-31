"""Intelligence package: Vision OCR providers and task consolidation."""

from rmcompanion.intelligence.provider import VisionProvider, get_vision_provider
from rmcompanion.intelligence.task_extractor import TaskExtractor

__all__ = ["VisionProvider", "get_vision_provider", "TaskExtractor"]
