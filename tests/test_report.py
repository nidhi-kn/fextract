"""Batch output naming regressions."""

import json
import csv
from pathlib import Path

from fextract.report import write_results
from fextract.schemas import DocumentResult, FieldValue, SectionResult


def _result(source_file: str) -> DocumentResult:
    """Create an empty fictional document result."""
    return DocumentResult(
        source_file=source_file,
        page_count=0,
        extraction_paths={},
        sections=[],
    )


def test_same_stem_different_extensions_get_distinct_json_outputs(tmp_path: Path):
    write_results(
        [_result("scan.png"), _result("scan.jpg"), _result("other.pdf")],
        tmp_path,
        {"json"},
    )

    assert sorted(path.name for path in tmp_path.glob("*.json")) == [
        "other.json",
        "scan.jpg.json",
        "scan.png.json",
        "summary.json",
    ]
    assert (
        json.loads((tmp_path / "scan.png.json").read_text())["source_file"]
        == "scan.png"
    )
    assert (
        json.loads((tmp_path / "scan.jpg.json").read_text())["source_file"]
        == "scan.jpg"
    )


def test_csv_outputs_use_plain_scalars_and_flat_table_columns(tmp_path: Path):
    result = _result("fictional.pdf")
    result.sections = [
        SectionResult(
            doc_type="commercial_invoice",
            doc_type_confidence=0.99,
            pages=[1],
            fields={
                "vendor_name": FieldValue(value="Fictional Vendor Ltd"),
                "missing_field": FieldValue(value=None),
            },
            tables={
                "line_items": [
                    {"part_number": "PX-1", "description": "Blue widget", "qty": 2}
                ],
                "other_rows": [{"label": "Subtotal", "amount": 12.5}],
            },
        ),
        SectionResult(
            doc_type="bank_statement",
            doc_type_confidence=0.98,
            pages=[2],
            fields={},
            tables={"transactions": [{"txn_date": "2025-01-02", "debit": 3.5}]},
        ),
    ]

    write_results([result], tmp_path, {"csv"})

    with (tmp_path / "fields.csv").open(newline="", encoding="utf-8") as handle:
        field_rows = list(csv.DictReader(handle))
    values = {row["field"]: row["value"] for row in field_rows}
    assert values["vendor_name"] == "Fictional Vendor Ltd"
    assert values["missing_field"] == ""
    with (tmp_path / "line_items.csv").open(newline="", encoding="utf-8") as handle:
        line_items = list(csv.DictReader(handle))
    assert line_items[0]["part_number"] == "PX-1"
    assert line_items[0]["qty"] == "2"
    with (tmp_path / "transactions.csv").open(newline="", encoding="utf-8") as handle:
        transactions = list(csv.DictReader(handle))
    assert transactions[0]["txn_date"] == "2025-01-02"
    with (tmp_path / "tables.csv").open(newline="", encoding="utf-8") as handle:
        generic = list(csv.DictReader(handle))
    assert generic[0]["label"] == "Subtotal"
    assert generic[0]["amount"] == "12.5"
