"""Text quality triage tests."""

from fextract.ingest.triage import (
    prefer_ocr_source,
    score_text,
    text_quality_score,
)


def test_clean_text_is_digital():
    assert (
        score_text("Balance sheet assets liabilities total assets 123,456").decision
        == "digital"
    )


def test_empty_text_requests_ocr():
    assert score_text("").decision == "ocr"


def test_low_quality_requests_ocr():
    assert score_text("%%%%%% $$$$ @@@@ ###").decision == "ocr"


def test_quality_comparison_includes_ocr_confidence():
    embedded = text_quality_score(0.80, 0.01)
    fresh_ocr = text_quality_score(0.79, 0.01, 0.95)
    assert fresh_ocr > embedded


def test_source_selection_prefers_only_available_better_ocr():
    assert prefer_ocr_source(0.8, 0.9, True, True)
    assert not prefer_ocr_source(0.9, 0.8, True, True)
    assert prefer_ocr_source(0.0, 0.0, False, True)
    assert not prefer_ocr_source(0.8, 0.95, True, False)
