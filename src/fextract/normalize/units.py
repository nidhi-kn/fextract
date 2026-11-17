"""Helpers for detecting and inheriting financial statement units."""

import re

from fextract.schemas import FieldValue

_UNIT_PATTERN = re.compile(r"\b(crores?|lakhs?|lacs?|thousands?)\b", re.I)


def detect_unit(text: str) -> str | None:
    """Return a statement multiplier or plain rupee unit when stated."""
    match = _UNIT_PATTERN.search(text)
    if match:
        unit = match.group(1).casefold()
        if unit.startswith("crore"):
            return "crores"
        if unit.startswith(("lakh", "lac")):
            return "lakhs"
        return "thousands"
    if re.search(r"\b(?:rupees?|inr)\b|₹|\brs\.?\b", text, re.I):
        return "rupees"
    return None


def inherited_unit(unit: str, page: int) -> FieldValue:
    """Build lower-confidence provenance for a document-inherited unit."""
    return FieldValue(
        value=unit,
        confidence=0.6,
        page=page,
        source="derived",
        flags=["inherited"],
    )
