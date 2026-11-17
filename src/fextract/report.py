"""JSON, field CSV, table CSV, and batch summary writers."""

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable
from fextract.schemas import DocumentResult


def _csv_cell(value: Any) -> Any:
    """Keep scalar values native for CSV; leave null cells empty."""
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    return json.dumps(value, ensure_ascii=False)


def _write_flat_rows(
    path: Path, rows: list[dict[str, Any]], base_fields: list[str]
) -> None:
    """Write dict rows using a stable metadata prefix and discovered columns."""
    fields = list(base_fields)
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_cell(value) for key, value in row.items()})


def write_results(
    results: Iterable[DocumentResult], output: Path, formats: set[str]
) -> None:
    """Write individual JSON and flattened CSV output files."""
    output.mkdir(parents=True, exist_ok=True)
    results = list(results)
    stem_counts = Counter(
        Path(result.source_file).stem.casefold() for result in results
    )
    if "json" in formats:
        for result in results:
            source = Path(result.source_file)
            suffix = (
                f".{source.suffix.lstrip('.')}"
                if stem_counts[source.stem.casefold()] > 1
                else ""
            )
            (output / f"{source.stem}{suffix}.json").write_text(
                result.model_dump_json(indent=2), encoding="utf-8"
            )
    if "csv" in formats:
        field_rows, line_item_rows, transaction_rows, generic_rows = [], [], [], []
        for result in results:
            for section_index, section in enumerate(result.sections, start=1):
                for name, item in section.fields.items():
                    field_rows.append(
                        {
                            "file": result.source_file,
                            "section": section_index,
                            "doc_type": section.doc_type,
                            "field": name,
                            "value": item.value,
                            "confidence": item.confidence,
                            "flagged": bool(item.flags),
                            "source": item.source,
                            "page": item.page,
                            "null_reason": item.null_reason,
                        }
                    )
                for name, table in section.tables.items():
                    target = (
                        line_item_rows
                        if name == "line_items"
                        else (
                            transaction_rows if name == "transactions" else generic_rows
                        )
                    )
                    for row in table:
                        flattened = dict(row) if isinstance(row, dict) else {"row": row}
                        target.append(
                            {
                                "file": result.source_file,
                                "section": section_index,
                                "doc_type": section.doc_type,
                                "table": name,
                                **flattened,
                            }
                        )
        _write_flat_rows(
            output / "fields.csv",
            field_rows,
            [
                "file",
                "section",
                "doc_type",
                "field",
                "value",
                "confidence",
                "flagged",
                "source",
                "page",
                "null_reason",
            ],
        )
        _write_flat_rows(
            output / "line_items.csv",
            line_item_rows,
            ["file", "section", "doc_type"],
        )
        _write_flat_rows(
            output / "transactions.csv",
            transaction_rows,
            ["file", "section", "doc_type"],
        )
        _write_flat_rows(
            output / "tables.csv",
            generic_rows,
            ["file", "section", "doc_type", "table"],
        )
    summary = {
        "documents": len(results),
        "errors": sum(bool(result.errors) for result in results),
        "needs_review": sum(bool(result.needs_review) for result in results),
        "pages": sum(result.page_count for result in results),
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
