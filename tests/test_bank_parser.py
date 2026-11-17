"""Bank statement parser regression tests."""

from fextract.extract.parsers.bank_statement import (
    parse_bank_positioned_pages,
    parse_bank_statement,
)
from fextract.classify.page_classifier import classify_page
from fextract.extract.parsers.invoice import parse_invoice


def test_bank_rows_and_derived_balances():
    fields, rows = parse_bank_statement(
        "01/01/2024 Shop 100.00 900.00\n02/01/2024 Salary 1,000.00 1,900.00"
    )
    assert len(rows) == 2
    # Flattened text has lost column positions, so amount direction/balances
    # are deliberately left null instead of being guessed.
    assert fields["opening_balance"].value is None
    assert all(row["debit"] is None and row["balance"] is None for row in rows)
    assert fields["closing_balance"].value is None
    assert fields["account_holder"].null_reason == "not_present"


def test_positioned_bank_amounts_follow_header_columns_and_derive_balances():
    lines = [
        [
            ("Statement", 10, -10),
            ("Period:", 60, -10),
            ("01/02/2025", 110, -10),
            ("-", 180, -10),
            ("01/02/2025", 200, -10),
        ],
        [
            ("Txn", 10, 10),
            ("Date", 35, 10),
            ("Description", 100, 10),
            ("Debit", 300, 10),
            ("Credit", 400, 10),
            ("Balance", 500, 10),
        ],
        [
            ("01/02/2025", 10, 30),
            ("Synthetic", 100, 30),
            ("purchase", 150, 30),
            ("100.00", 300, 30),
            ("0.00", 400, 30),
            ("900.00", 500, 30),
        ],
        [("wrapped", 100, 50), ("detail", 150, 50)],
    ]
    words = {
        1: [
            {"text": text, "x0": x, "x1": x + len(text) * 4, "top": y}
            for line in lines
            for text, x, y in line
        ]
    }
    fields, rows = parse_bank_positioned_pages(words, [1])
    assert rows == [
        {
            "txn_date": "2025-02-01",
            "value_date": None,
            "cheque_no": None,
            "description": "Synthetic purchase wrapped detail",
            "branch_code": None,
            "debit": 100.0,
            "credit": 0.0,
            "balance": 900.0,
            "page": 1,
        }
    ]
    assert fields["period_start"].value == "2025-02-01"
    assert fields["period_end"].value == "2025-02-01"
    assert fields["opening_balance"].value == 1000.0
    assert fields["opening_balance"].source == "derived"
    assert fields["closing_balance"].value == 900.0


def test_missing_ocr_debit_column_keeps_opening_balance_null():
    words = {
        1: [
            {"text": text, "x0": x, "x1": x + 10, "top": y}
            for text, x, y in (
                ("Statement", 10, 0),
                ("Period:", 70, 0),
                ("01/02/2025", 120, 0),
                ("Txn", 10, 20),
                ("Date", 30, 20),
                ("Description", 100, 20),
                ("Credit", 300, 20),
                ("Balance", 400, 20),
                ("01/02/2025", 10, 50),
                ("Purchase", 100, 50),
                ("0.00", 300, 50),
                ("900.00", 400, 50),
            )
        ]
    }
    fields, rows = parse_bank_positioned_pages(words, [1])
    assert fields["closing_balance"].value == 900.0
    assert fields["opening_balance"].value is None
    assert rows[0]["debit"] is None


def test_degraded_vendor_punctuation_is_trimmed():
    fields = parse_invoice("COMMERCIAL INVOICE\nVendor: Example Supplier 17°")
    assert fields["vendor_name"].value == "Example Supplier 17"


def test_partial_bank_header_still_classifies_from_remaining_columns():
    label, confidence = classify_page(
        "BANK STATEMENT\nTxn Date Description Credit Balance"
    )
    assert label == "bank_statement"
    assert confidence >= 0.9
