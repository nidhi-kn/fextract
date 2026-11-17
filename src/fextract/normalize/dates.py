"""Date parsing helpers that produce ISO 8601 calendar dates."""

from datetime import datetime
import re

_FORMATS = (
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%Y-%m-%d",
    "%d/%m/%y",
    "%d-%b-%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%B %d, %Y",
)


def normalize_date(raw: str | None) -> str | None:
    """Convert a supported finance date to YYYY-MM-DD, or return None."""
    if not raw:
        return None
    value = " ".join(raw.strip().replace(",", " ").split())
    value = re.sub(r"\b(\d{1,2})(?:st|nd|rd|th)\b", r"\1", value, flags=re.I)
    value = re.sub(r"\b(\d{1,2})(?:st|nd|rd|th)\b", r"\1", value, flags=re.I)
    for fmt in _FORMATS:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None
