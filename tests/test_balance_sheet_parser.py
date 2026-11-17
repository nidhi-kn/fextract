"""Balance sheet parser regression tests."""

from fextract.extract.parsers.balance_sheet import parse_balance_sheet
from fextract.extract.parsers.balance_sheet import parse_balance_sheet_totals_words


def test_balance_sheet_totals():
    fields = parse_balance_sheet(
        "Balance Sheet\nTotal Assets 10,000\nTotal Liabilities 10,000"
    )
    assert fields["total_assets"].value == 10000
    assert fields["total_liabilities"].value == 10000


def test_equity_and_liabilities_total_synonym():
    fields = parse_balance_sheet(
        "Balance Sheet\nTotal Assets 22,222\nTotal equity and liabilities 22,222"
    )
    assert fields["total_assets"].value == 22222
    assert fields["total_liabilities"].value == 22222


def test_totals_at_bottom_are_recovered_when_pdf_serializes_columns_separately():
    fields = parse_balance_sheet(
        "Balance Sheet\nTOTAL\nASSETS\nTOTAL\nLIABILITIES\n"
        "Figures for current period\n3,219.00\n77,777.00\n77,777.00\n"
        "IN TERMS OF OUR ATTACHED REPORT\nFor Example Audit LLP"
    )
    assert fields["total_assets"].value == 77777
    assert fields["total_liabilities"].value == 77777


def test_positioned_totals_are_assigned_to_their_statement_side():
    words = [
        {"text": "LIABILITIES", "x0": 20, "x1": 80, "top": 10},
        {"text": "TOTAL", "x0": 200, "x1": 230, "top": 40},
        {"text": "77,777.00", "x0": 350, "x1": 400, "top": 40},
        {"text": "ASSETS", "x0": 20, "x1": 60, "top": 60},
        {"text": "TOTAL", "x0": 200, "x1": 230, "top": 90},
        {"text": "77,777.00", "x0": 350, "x1": 400, "top": 90},
    ]
    fields = parse_balance_sheet_totals_words(words)
    assert fields["total_assets"].value == 77777
    assert fields["total_liabilities"].value == 77777


def test_as_at_ordinal_date_is_normalized():
    fields = parse_balance_sheet("Balance Sheet\nAs at 31st March, 2022")

    assert fields["as_on_date"].value == "2022-03-31"
