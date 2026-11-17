"""Locale-tolerant numeric parsing for finance documents."""

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class NormalizedNumber:
    """Parsed numeric value and any scale/currency metadata."""

    value: float | None
    unit: str | None = None
    currency: str | None = None


_CURRENCIES = {
    "₹": "INR",
    "rs.": "INR",
    "rs": "INR",
    "inr": "INR",
    "usd": "USD",
    "$": "USD",
    "gbp": "GBP",
    "£": "GBP",
    "eur": "EUR",
    "€": "EUR",
}
_UNITS = (
    (r"\b(?:crores?|cr)\b", "crores", 10_000_000),
    (r"\b(?:lakhs?|lacs?|l)\b", "lakhs", 100_000),
    (r"\b(?:thousands?|in\s+000s?)\b", "thousands", 1_000),
)


def normalize_number(raw: str | int | float | None) -> NormalizedNumber:
    """Parse Indian/Western grouped numbers, negatives, currencies, and units."""
    if raw is None:
        return NormalizedNumber(None)
    if isinstance(raw, (int, float)):
        return NormalizedNumber(float(raw))
    text = str(raw).strip().replace("\u00a0", " ")
    if not text or text in {"-", "–", "—", "−"}:
        return NormalizedNumber(None)
    currency = next(
        (code for symbol, code in _CURRENCIES.items() if symbol in text.lower()), None
    )
    unit, multiplier = None, 1
    for pattern, name, scale in _UNITS:
        if re.search(pattern, text, flags=re.I):
            unit, multiplier = name, scale
            text = re.sub(pattern, "", text, flags=re.I)
            break
    for symbol in _CURRENCIES:
        text = re.sub(re.escape(symbol), "", text, flags=re.I)
    text = re.sub(r"\b(?:INR|USD|GBP|EUR)\b", "", text, flags=re.I)
    text = text.strip().replace(",", "").replace(" ", "")
    negative = text.startswith("(") and text.endswith(")") or text.endswith("-")
    text = text.strip("()")
    if text.endswith("-"):
        text = text[:-1]
    if text.startswith("-"):
        negative = True
        text = text[1:]
    if not re.fullmatch(r"\d+(?:\.\d+)?", text):
        return NormalizedNumber(None, unit, currency)
    value = float(text) * multiplier
    return NormalizedNumber(-value if negative else value, unit, currency)
