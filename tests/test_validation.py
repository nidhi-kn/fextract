"""Arithmetic checks and confidence tests."""

import pytest
from fextract.schemas import FieldValue
from fextract.validate.checks import validate_section
from fextract.validate.confidence import score_confidence
from fextract.validate.confidence import flag_fields


def test_balance_sheet_mismatch_fails():
    fields = {
        "total_assets": FieldValue(value=10),
        "total_liabilities": FieldValue(value=8),
    }
    assert validate_section("balance_sheet", fields, {})[0].passed is False


def test_confidence_formula():
    assert score_confidence(1, 0.5, 1) == pytest.approx(0.85)


def test_corrupted_running_balance_fails():
    fields = {"opening_balance": FieldValue(value=100)}
    rows = [
        {"txn_date": "2024-01-01", "debit": 10, "credit": 0, "balance": 90},
        {"txn_date": "2024-01-02", "debit": 5, "credit": 0, "balance": 75},
    ]
    result = validate_section("bank_statement", fields, {"transactions": rows})
    assert result[-1].passed is False


def test_profit_loss_is_not_evaluable_when_statement_components_are_missing():
    fields = {
        "revenue": FieldValue(value=520),
        "expenses": FieldValue(value=410),
        "profit_before_tax": FieldValue(value=110),
        "profit": FieldValue(value=85),
    }

    results = validate_section("profit_and_loss", fields, {})

    assert [result.passed for result in results] == [None, None]
    assert [result.status for result in results] == ["not_evaluable", "not_evaluable"]


def test_profit_loss_full_reconciliation_passes_or_fails_only_on_complete_values():
    fields = {
        "revenue": FieldValue(value=520),
        "other_income": FieldValue(value=10),
        "expenses": FieldValue(value=410),
        "exceptional_items": FieldValue(value=-5),
        "profit_before_tax": FieldValue(value=115),
        "tax_expense": FieldValue(value=-25),
        "profit": FieldValue(value=90),
    }

    results = validate_section("profit_and_loss", fields, {})
    assert [result.passed for result in results] == [True, True]

    fields["profit"] = FieldValue(value=89)
    results = validate_section("profit_and_loss", fields, {})
    assert [result.passed for result in results] == [True, False]


def test_failed_check_flags_only_fields_bound_to_that_check():
    fields = {
        "total_assets": FieldValue(value=10, source="rule"),
        "total_liabilities": FieldValue(value=8, source="rule"),
        "entity_name": FieldValue(value="Example Trading Ltd", source="rule"),
    }
    validations = validate_section("balance_sheet", fields, {})
    flagged = flag_fields(fields, validations, threshold=0.7, source_score=1.0)
    assert set(flagged) == {"total_assets", "total_liabilities"}
    assert "review" not in fields["entity_name"].flags


def test_source_disagreement_is_flagged_even_if_confidence_is_high():
    fields = {
        "revenue": FieldValue(value=100, flags=["source_disagreement"], source="rule"),
        "expenses": FieldValue(value=20, source="rule"),
    }
    assert flag_fields(fields, [], threshold=0.7, source_score=1.0) == ["revenue"]
