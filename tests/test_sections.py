"""Page-to-section grouping tests."""

from fextract.classify.sections import group_sections
from fextract.classify.page_classifier import classify_page


def test_adjacent_pages_split_on_classification_change():
    result = group_sections(
        [("audit_report", 0.96), ("audit_report", 0.95), ("balance_sheet", 0.96)]
    )
    assert [section["pages"] for section in result] == [[1, 2], [3]]


def test_weak_page_cannot_start_a_new_section():
    result = group_sections(
        [
            ("audit_report", 0.96),
            ("profit_and_loss", 0.78),
            ("notes_other", 0.97),
            ("profit_and_loss", 0.78),
        ]
    )
    assert [(section["doc_type"], section["pages"]) for section in result] == [
        ("audit_report", [1, 2]),
        ("notes_other", [3, 4]),
    ]


def test_notes_prose_does_not_start_false_profit_and_loss_section():
    label, confidence = classify_page(
        "NOTES to the financial statements\n"
        "Accounting policies refer to the Statement of Profit and Loss."
    )
    assert (label, confidence) == ("notes_other", 0.97)


def test_notes_heading_takes_precedence_over_incidental_statement_heading():
    label, confidence = classify_page(
        "NOTES to the financial statements\n"
        "Statement of Profit and Loss\n"
        "The note explains amounts presented in the statement."
    )

    assert label == "notes_other"
    assert confidence >= 0.9


def test_proprietor_profit_transfer_schedule_is_not_a_new_profit_loss_section():
    label, confidence = classify_page(
        "PARTICULAR AMT\nBy Gross Receipts 520.00\n"
        "To Direct Purchase 310.00\nTo Net Profit Transfer to capital A/c 90.00\n"
        "PROFIT AND LOSS ACCOUNT FOR THE YEAR ENDED 31 MARCH 2025"
    )

    assert label == "notes_other"
    assert confidence >= 0.9


def test_generic_totals_and_asset_words_do_not_start_balance_sheet_section():
    label, confidence = classify_page(
        "Current Liabilities\nOther Current Liabilities\nTotal\nNotes 6\n"
        "Non Current Investments\nInvestments in shares\nTotal\n"
        "Long Term Loans and Advances\nOther Non Current Assets\nTotal"
    )

    assert label == "notes_other"
    assert confidence < 0.9


def test_low_signal_statement_candidate_merges_into_previous_section():
    result = group_sections(
        [
            ("profit_and_loss", 0.96),
            ("balance_sheet", 0.35),
            ("cash_flow_statement", 0.96),
        ]
    )

    assert [(section["doc_type"], section["pages"]) for section in result] == [
        ("profit_and_loss", [1, 2]),
        ("cash_flow_statement", [3]),
    ]


def test_weak_continuation_does_not_reduce_section_type_confidence():
    result = group_sections(
        [("balance_sheet", 0.96), ("notes_other", 0.35), ("balance_sheet", 0.94)]
    )

    assert len(result) == 1
    assert result[0]["doc_type"] == "balance_sheet"
    assert result[0]["pages"] == [1, 2, 3]
    assert result[0]["doc_type_confidence"] == 0.95
