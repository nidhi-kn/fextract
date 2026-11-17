"""Cash flow parser regression tests."""

from fextract.extract.parsers.cash_flow import (
    parse_cash_flow,
    parse_cash_flow_positioned,
)
from fextract.validate.checks import validate_section


def test_cash_flow_values():
    fields = parse_cash_flow(
        "Cash flow statement\nNet change 500\nCash at beginning 1,000\nCash at end 1,500"
    )
    assert fields["net_change"].value == 500
    assert fields["opening_cash"].value == 1000


def test_cash_summary_uses_period_columns_and_ignores_refer_note_number():
    words = [
        {"text": "Note", "x0": 200, "x1": 220, "top": 10},
        {"text": "2024", "x0": 300, "x1": 325, "top": 10},
        {"text": "2023", "x0": 400, "x1": 425, "top": 10},
        {
            "text": "Net increase/(decrease) in cash and cash equivalents",
            "x0": 20,
            "x1": 190,
            "top": 30,
        },
        {"text": "10", "x0": 300, "x1": 310, "top": 30},
        {"text": "(5)", "x0": 400, "x1": 425, "top": 30},
        {
            "text": "Cash and cash equivalents at the beginning of the year",
            "x0": 20,
            "x1": 190,
            "top": 50,
        },
        {"text": "note", "x0": 200, "x1": 220, "top": 50},
        {"text": "7", "x0": 225, "x1": 235, "top": 50},
        {"text": "900", "x0": 300, "x1": 320, "top": 50},
        {"text": "800", "x0": 400, "x1": 420, "top": 50},
        {
            "text": "Cash and cash equivalents at the end of the year",
            "x0": 20,
            "x1": 190,
            "top": 70,
        },
        {"text": "note", "x0": 200, "x1": 220, "top": 70},
        {"text": "7", "x0": 225, "x1": 235, "top": 70},
        {"text": "910", "x0": 300, "x1": 320, "top": 70},
        {"text": "795", "x0": 400, "x1": 420, "top": 70},
    ]
    fields = parse_cash_flow_positioned({1: words})
    assert fields["net_change"].value == 10
    assert fields["opening_cash"].value == 900
    assert fields["closing_cash"].value == 910


def test_activity_totals_accept_direction_variants_bracket_tags_and_negatives():
    fields = parse_cash_flow(
        "Net cash (used in) / generated from operating activities - [A] 5,916\n"
        "Net cash (used in) / generated from investing activities - [B] (1,264)\n"
        "Net cash (used in) generated financing activities - [C] (4,651)\n"
        "Net increase/(decrease) in cash and cash equivalents 1"
    )

    assert fields["operating_activities"].value == 5916
    assert fields["investing_activities"].value == -1264
    assert fields["financing_activities"].value == -4651
    check = next(
        result
        for result in validate_section("cash_flow_statement", fields, {})
        if result.check == "activities_sum_equals_net_change"
    )
    assert check.passed is True


def test_activity_values_on_following_rows_are_collected_with_prior_period():
    fields = parse_cash_flow(
        "Net cash (used in) / generated from operating activities - [A]\n"
        "5,916\n4,953\n"
        "Net cash (used in) / generated from investing activities - [B]\n"
        "(1,264)\n(752)\n"
        "Net cash (used in) generated financing activities - [C]\n"
        "(4,651)\n(4,264)\n"
        "Net increase/(decrease) in cash and cash equivalents - [A+B+C]\n1\n(63)"
    )

    assert fields["operating_activities"].value == 5916
    assert fields["operating_activities_prior_year"].value == 4953
    assert fields["investing_activities"].value == -1264
    assert fields["financing_activities"].value == -4651
    assert fields["net_change"].value == 1


def test_cash_summary_ignores_note_reference_and_preserves_bracketed_sign():
    fields = parse_cash_flow(
        "Net increase/(decrease) in cash and cash equivalents\n"
        "(1,526.31)\n775.18\n"
        "Cash and cash equivalents at the beginning of year (refer Note\n"
        "3\n1,547.52\n772.34\n"
        "Cash and cash equivalents at the end of year (refer Note 3)\n"
        "21.21\n1,547.52"
    )

    assert fields["net_change"].value == -1526.31
    assert fields["net_change_prior_year"].value == 775.18
    assert fields["opening_cash"].value == 1547.52
    assert fields["closing_cash"].value == 21.21
