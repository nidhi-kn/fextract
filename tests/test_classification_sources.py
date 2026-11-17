"""Synthetic regressions for classifying across embedded and OCR sources."""

from fextract.classify.page_classifier import classify_page_sources


def test_embedded_notes_heading_overrides_ocr_false_balance_sheet_signal():
    result = classify_page_sources(
        (
            "NOTES to the financial statements for the year ended. Tax Assets and Liabilities",
            "Balance Sheet Total Assets Liabilities 100",
        )
    )
    assert result == ("notes_other", 0.97)


def test_stronger_ocr_statement_heading_beats_weak_embedded_text():
    result = classify_page_sources(
        ("body text with few clues", "Statement of Profit and Loss\nRevenue Expenses")
    )
    assert result == ("profit_and_loss", 0.99)
