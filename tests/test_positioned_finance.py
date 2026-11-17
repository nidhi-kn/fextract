"""Synthetic period-column mapping tests with a note-reference column."""

from fextract.extract.parsers.profit_loss import parse_profit_loss_positioned


def test_profit_loss_maps_amounts_to_current_and_prior_year_columns():
    words = [
        {"text": "Note", "x0": 200, "x1": 220, "top": 10},
        {"text": "2024", "x0": 300, "x1": 325, "top": 10},
        {"text": "2023", "x0": 400, "x1": 425, "top": 10},
        {"text": "Revenue from operations", "x0": 20, "x1": 180, "top": 30},
        {"text": "25", "x0": 205, "x1": 215, "top": 30},
        {"text": "123,456", "x0": 300, "x1": 340, "top": 30},
        {"text": "113,333", "x0": 400, "x1": 440, "top": 30},
        {"text": "Total expenses", "x0": 20, "x1": 150, "top": 50},
        {"text": "31", "x0": 205, "x1": 215, "top": 50},
        {"text": "87,000", "x0": 300, "x1": 340, "top": 50},
        {"text": "84,000", "x0": 400, "x1": 440, "top": 50},
    ]
    fields = parse_profit_loss_positioned(words)
    assert fields["revenue"].value == 123456
    assert fields["revenue_prior_year"].value == 113333
    assert fields["expenses"].value == 87000


def test_revenue_from_other_operations_and_total_revenue_labels_are_supported():
    words = [
        {"text": "Note", "x0": 200, "x1": 220, "top": 10},
        {"text": "2024", "x0": 300, "x1": 325, "top": 10},
        {"text": "2023", "x0": 400, "x1": 425, "top": 10},
        {"text": "Revenue from other operations", "x0": 20, "x1": 190, "top": 30},
        {"text": "10", "x0": 205, "x1": 215, "top": 30},
        {"text": "123,456", "x0": 300, "x1": 340, "top": 30},
        {"text": "119,000", "x0": 400, "x1": 440, "top": 30},
    ]
    fields = parse_profit_loss_positioned(words)
    assert fields["revenue"].value == 123456


def test_total_revenue_synonym_is_supported():
    words = [
        {"text": "Note", "x0": 200, "x1": 220, "top": 10},
        {"text": "2024", "x0": 300, "x1": 325, "top": 10},
        {"text": "2023", "x0": 400, "x1": 425, "top": 10},
        {"text": "Total revenue", "x0": 20, "x1": 120, "top": 30},
        {"text": "125,750", "x0": 300, "x1": 340, "top": 30},
        {"text": "121,000", "x0": 400, "x1": 440, "top": 30},
    ]
    assert parse_profit_loss_positioned(words)["revenue"].value == 125750
