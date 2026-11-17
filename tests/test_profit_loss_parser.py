"""Fictional P&L component extraction cases."""

from fextract.extract.parsers.profit_loss import (
    parse_profit_loss,
    parse_profit_loss_positioned,
)
from fextract.validate.checks import validate_section


def test_extracts_components_needed_for_complete_profit_reconciliation():
    fields = parse_profit_loss(
        "Revenue from operations 520.00\n"
        "Other income 10.00\n"
        "Total expenses 410.00\n"
        "Exceptional items (5.00)\n"
        "Profit before tax 115.00\n"
        "Tax expense 25.00\n"
        "Profit for the year 90.00"
    )

    assert fields["revenue"].value == 520
    assert fields["other_income"].value == 10
    assert fields["expenses"].value == 410
    assert fields["exceptional_items"].value == -5
    assert fields["profit_before_tax"].value == 115
    assert fields["tax_expense"].value == 25
    assert fields["profit"].value == 90


def test_positioned_tax_components_are_summed_and_exceptional_label_is_unambiguous():
    words = []

    def add_row(y, label, current=None, prior=None):
        words.append({"text": label, "x0": 10, "x1": 250, "top": y, "bottom": y + 8})
        for x, value in ((400, current), (500, prior)):
            if value is not None:
                words.append(
                    {"text": value, "x0": x, "x1": x + 40, "top": y, "bottom": y + 8}
                )

    add_row(10, "Year ended", "2025", "2024")
    add_row(20, "Revenue from operations", "520", "500")
    add_row(30, "Other income", "10", "8")
    add_row(40, "Total expenses", "410", "390")
    add_row(50, "Profit before exceptional items and tax", "120", "118")
    add_row(60, "Exceptional items", "5", "2")
    add_row(70, "Profit before tax", "125", "120")
    add_row(80, "Tax expenses")
    add_row(90, "Current tax", "(30)", "(32)")
    add_row(100, "Deferred tax credit/(charge)", "5", "3")
    add_row(110, "Profit for the year", "100", "91")

    fields = parse_profit_loss_positioned(words)
    assert fields["exceptional_items"].value == 5
    assert fields["tax_expense"].value == -25
    assert fields["tax_expense_prior_year"].value == -29
    assert [
        result.passed for result in validate_section("profit_and_loss", fields, {})
    ] == [True, True]


def test_labelled_nil_totals_are_zero_and_marked_nil():
    fields = parse_profit_loss(
        "Revenue from operations 70\nTotal revenue -\n"
        "Total expenses nil\nProfit before tax (0)\nTax expense –\n"
        "Profit for the year 0"
    )

    assert fields["revenue"].value == 0
    assert fields["revenue"].flags == ["nil"]
    assert fields["expenses"].value == 0
    assert fields["expenses"].flags == ["nil"]
    assert fields["tax_expense"].value == 0
    assert fields["tax_expense"].flags == ["nil"]


def test_positioned_nil_period_cell_is_zero_and_marked_nil():
    words = []
    for text, x in (("Year", 20), ("2025", 400), ("2024", 500)):
        words.append({"text": text, "x0": x, "x1": x + 30, "top": 10, "bottom": 18})
    for text, x in (("Total", 20), ("revenue", 55), ("-", 400), ("12", 500)):
        words.append({"text": text, "x0": x, "x1": x + 30, "top": 20, "bottom": 28})

    fields = parse_profit_loss_positioned(words)
    assert fields["revenue"].value == 0
    assert fields["revenue"].flags == ["nil"]
    assert fields["revenue_prior_year"].value == 12


def test_omitted_components_are_derived_only_from_printed_totals():
    fields = parse_profit_loss(
        "Revenue from operations\nNote 7\n81,250.00\n"
        "Other income\nTotal revenue 81,250.00\n"
        "Total expenses 129,770.00\nProfit before tax (48,520.00)\n"
        "Tax expense\nCurrent tax\nProfit for the year (48,520.00)"
    )

    assert fields["other_income"].value == 0
    assert fields["other_income"].source == "derived"
    assert fields["exceptional_items"].value == 0
    assert fields["tax_expense"].value == 0
    checks = validate_section("profit_and_loss", fields, {})
    assert [check.passed for check in checks] == [True, True]


def test_note_reference_before_grouped_amount_is_not_extracted_as_value():
    fields = parse_profit_loss(
        "Revenue from other operations\n17\n123,456.00\n"
        "Total expenses 190,000.00\nProfit before tax (66,544.00)"
    )

    assert fields["revenue"].value == 123456
