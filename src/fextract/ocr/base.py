"""Shared OCR types and protocol."""

from dataclasses import dataclass
from typing import Protocol, Any


@dataclass
class OCRWord:
    """OCR token with page coordinates and engine confidence."""

    text: str
    bbox: list[float]
    confidence: float


class OCREngine(Protocol):
    """Common interface for locally installed OCR engines."""

    def run(self, image: Any) -> list[OCRWord]: ...
