"""Per-page embedded text quality scoring."""

from dataclasses import asdict, dataclass
import re


@dataclass
class PageTriage:
    """Text-layer metrics and selected processing path for a page."""

    page: int
    char_count: int
    dictionary_ratio: float
    garbage_ratio: float
    has_full_page_image: bool
    decision: str


def text_quality_score(
    dictionary_ratio: float, garbage_ratio: float, source_confidence: float = 0.75
) -> float:
    """Combine text legibility metrics and source confidence into a page score."""
    return max(
        0.0,
        min(
            1.0,
            0.5 * dictionary_ratio
            + 0.25 * (1.0 - garbage_ratio)
            + 0.25 * source_confidence,
        ),
    )


def prefer_ocr_source(
    embedded_quality: float,
    ocr_quality: float,
    has_embedded_text: bool,
    has_words: bool,
) -> bool:
    """Select OCR only when available and measurably better than embedded text."""
    return has_words and (
        not has_embedded_text or ocr_quality > embedded_quality + 0.005
    )


def numeric_token_count(text: str) -> int:
    """Count finance-like numeric tokens without counting isolated punctuation."""
    return len(re.findall(r"(?<!\w)[+-]?\(?\d[\d,]*(?:\.\d+)?\)?-?(?!\w)", text))


def choose_text_source(
    embedded_text: str,
    ocr_text: str,
    embedded_quality: float,
    ocr_quality: float,
    embedded_validation: list[bool | None] | None = None,
    ocr_validation: list[bool | None] | None = None,
) -> str:
    """Choose a text layer by validation, numeric retention, then text quality."""
    if not ocr_text.strip():
        return "embedded_text" if embedded_text.strip() else "ocr_unavailable"
    if not embedded_text.strip():
        return "ocr"

    def validation_score(results: list[bool | None] | None) -> float:
        evaluable = [value for value in (results or []) if value is not None]
        return sum(evaluable) / len(evaluable) if evaluable else 0.5

    embedded_numbers = numeric_token_count(embedded_text)
    ocr_numbers = numeric_token_count(ocr_text)
    retention = min(1.0, ocr_numbers / max(embedded_numbers, 1))
    embedded_score = (
        0.2 * validation_score(embedded_validation) + 0.4 + 0.4 * embedded_quality
    )
    ocr_score = (
        0.2 * validation_score(ocr_validation) + 0.4 * retention + 0.4 * ocr_quality
    )
    return "ocr" if ocr_score > embedded_score + 0.005 else "embedded_text"


def score_text(
    text: str, page: int = 1, has_full_page_image: bool = False
) -> PageTriage:
    """Score whether embedded page text is reliable enough for extraction."""
    tokens = re.findall(r"[\w₹$£€.,()-]+", text, flags=re.UNICODE)
    valid = sum(
        bool(re.fullmatch(r"[A-Za-z]{2,}|\d+(?:[,.]\d+)*|[₹$£€()-]+", token))
        for token in tokens
    )
    dictionary = valid / max(len(tokens), 1)
    garbage = sum(
        not (c.isalnum() or c.isspace() or c in "₹$£€.,:;()/-") for c in text
    ) / max(len(text), 1)
    if len(text.strip()) < 20 or dictionary < 0.55 or garbage > 0.12:
        decision = "ocr"
    elif has_full_page_image and (dictionary < 0.80 or garbage > 0.01):
        decision = "ocr"
    elif has_full_page_image:
        # Full-page imagery alone is not evidence that a good text layer needs
        # OCR. Preserve a clean embedded layer and reserve OCR for weak pages.
        decision = "digital"
    elif dictionary < 0.72:
        decision = "hybrid"
    else:
        decision = "digital"
    return PageTriage(
        page, len(text), dictionary, garbage, has_full_page_image, decision
    )


def triage_page(
    text: str, page: int = 1, has_full_page_image: bool = False
) -> dict[str, object]:
    """Return a JSON-friendly page quality record."""
    return asdict(score_text(text, page, has_full_page_image))
