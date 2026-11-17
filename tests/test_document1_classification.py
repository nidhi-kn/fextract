"""Redacted classification cases for sole-proprietor statement pages."""

from fextract.classify.page_classifier import classify_page


def test_balance_sheet_with_adjacent_assets_and_liabilities_is_strong_signal():
    label, confidence = classify_page(
        "Name Of Entity\nPrevious Year 2022-23\nLiabilities Amt\n"
        "Capital Account 4612930\nAssets Amt\nFixed Assets 505600\n"
    )
    assert label == "balance_sheet"
    assert confidence >= 0.9


def test_capital_account_rollforward_stays_generic_notes_type():
    label, confidence = classify_page(
        "Particular AMT\nBy Balance b/d 1000\nBy Net Profit Transfer 300\n"
        "To Drawings 100\nTo Balance C/f 1200"
    )
    assert label == "notes_other"
    assert confidence >= 0.9
