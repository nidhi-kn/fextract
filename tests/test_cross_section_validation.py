"""Synthetic cross-section accounting reconciliations."""

from fextract.schemas import FieldValue, SectionResult, ValidationResult
from fextract.validate.cross_section import validate_cross_sections


def word(text, x, y, width=20):
    return {"text": text, "x0": x, "x1": x + width, "top": y}


def test_cross_section_reconciliations_pass_with_fictional_values():
    sections = [
        SectionResult(
            doc_type="balance_sheet",
            doc_type_confidence=0.99,
            pages=[3],
            fields={},
        ),
        SectionResult(
            doc_type="profit_and_loss",
            doc_type_confidence=0.99,
            pages=[2],
            fields={"profit": FieldValue(value=-9_840)},
        ),
        SectionResult(
            doc_type="notes_other",
            doc_type_confidence=0.9,
            pages=[1, 4],
            fields={},
        ),
    ]
    page_texts = {
        1: "Reserves and surplus\nClosing Balance\nCash and cash equivalents\nTotal",
        2: "Earnings per equity share\n(1.23)",
        3: "Balance Sheet",
        4: "Cash and cash equivalents\nTotal",
    }
    positioned = {
        1: [
            word("Closing", 10, 10),
            word("Balance", 50, 10),
            word("(9,840.00)", 140, 10),
        ],
        2: [
            word("Weighted", 10, 10),
            word("average", 60, 10),
            word("number", 110, 10),
            word("shares", 160, 10),
            word("8.000", 230, 10),
            word("00", 252, 10),
        ],
        3: [
            word("Cash", 10, 10),
            word("and", 50, 10),
            word("cash", 80, 10),
            word("equivalents", 110, 10),
            word("987.00", 220, 10),
        ],
        4: [word("Total", 10, 20), word("987.00", 220, 20)],
    }
    results = validate_cross_sections(sections, page_texts, positioned)
    assert [result.status for result in results] == ["passed", "passed", "passed"]


def test_cross_section_checks_report_not_evaluable_explicitly():
    results = validate_cross_sections([], {}, {})
    assert len(results) == 3
    assert all(result.passed is None for result in results)
    assert all(result.status == "not_evaluable" for result in results)


def test_validation_status_maps_true_and_false():
    assert ValidationResult(check="ok", passed=True).status == "passed"
    assert ValidationResult(check="bad", passed=False).status == "failed"
