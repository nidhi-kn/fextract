"""Synthetic regression cases for noisy scan classification and extraction."""

import json

from fextract.classify.page_classifier import classify_page
from fextract.extract.parsers.profit_loss import parse_profit_loss
from fextract.extract.llm import extract_missing_fields
from fextract.ingest.triage import choose_text_source
from fextract.validate.checks import validate_section


def test_numbered_note_page_is_not_false_balance_sheet():
    label, _ = classify_page(
        "Notes 5 Current Liabilities\nOther payables\nCash and cash equivalents"
    )
    assert label == "notes_other"


def test_full_statement_of_profit_and_loss_heading_is_strong_signal():
    label, confidence = classify_page(
        "Statement Of Profit and loss for the year ended on 31st March 2024\n"
        "Revenue\nExpenses"
    )
    assert label == "profit_and_loss"
    assert confidence >= 0.9


def test_independent_auditor_report_heading_starts_an_audit_section():
    label, confidence = classify_page("Independent Auditor's Report\nNotes on audit")
    assert label == "audit_report"
    assert confidence >= 0.9


def test_ocr_p_and_l_extracts_adjacent_amounts_without_skipping_labels():
    fields = parse_profit_loss(
        "Total expenses\n18,750.00\nProfit before tax\n(1,250.00)\n"
        "Profit (Loss) for the year (1,250.00)",
        page=7,
    )
    assert fields["expenses"].value == 18750
    assert fields["profit_before_tax"].value == -1250
    assert fields["profit"].value == -1250
    assert fields["revenue"].value is None


def test_llm_values_must_be_grounded_in_source(monkeypatch):
    response = {"response": json.dumps({"auditor_firm": "ACME AUDIT LLP"})}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self):
            return json.dumps(response).encode()

    monkeypatch.setattr(
        "fextract.extract.llm.urlopen", lambda *_a, **_k: FakeResponse()
    )
    assert extract_missing_fields(
        "ACME AUDIT LLP is the auditor.", ["auditor_firm"]
    ) == {"auditor_firm": "ACME AUDIT LLP"}
    assert extract_missing_fields("No firm is named.", ["auditor_firm"]) == {}


def test_llm_rejects_source_match_with_wrong_field_context(monkeypatch):
    response = {"response": json.dumps({"entity_name": "NORTHSTAR AUDIT LLP"})}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self):
            return json.dumps(response).encode()

    monkeypatch.setattr(
        "fextract.extract.llm.urlopen", lambda *_a, **_k: FakeResponse()
    )
    source = "NORTHSTAR AUDIT LLP Chartered Accountants signed the audit report."
    assert extract_missing_fields(source, ["entity_name"]) == {}


def test_source_arbitration_preserves_embedded_financial_amounts():
    embedded = "Assets 77,777.00\nLiabilities 77,777.00"
    fresh_ocr = "Assets 77,777.00\nLiabilities [box]"
    assert (
        choose_text_source(embedded, fresh_ocr, 0.82, 0.95, [True], [None])
        == "embedded_text"
    )


def test_profit_loss_arithmetic_is_a_source_selection_signal():
    fields = {
        "revenue": type("Value", (), {"value": 123456})(),
        "other_income": type("Value", (), {"value": 0})(),
        "expenses": type("Value", (), {"value": 130000})(),
        "exceptional_items": type("Value", (), {"value": 0})(),
        "profit_before_tax": type("Value", (), {"value": -6544})(),
        "tax_expense": type("Value", (), {"value": 0})(),
        "profit": type("Value", (), {"value": -6544})(),
    }
    checks = validate_section("profit_and_loss", fields, {})
    assert [check.passed for check in checks] == [True, True]


def test_embedded_profit_loss_rows_survive_note_column_serialization():
    fields = parse_profit_loss(
        "1 Revenue from other operations\n17\n123,456.00\n"
        "II Total expenses\n190,000.00\n"
        "III Profit before tax (1-11)\n(66,544.00)\n"
        "V Profit (Loss) for the year (66,544.00)"
    )
    assert fields["revenue"].value == 123456
    assert fields["expenses"].value == 190000
    assert fields["profit"].value == -66544
    checks = validate_section("profit_and_loss", fields, {})
    assert [check.passed for check in checks] == [None, None]
