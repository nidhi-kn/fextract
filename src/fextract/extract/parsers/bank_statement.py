"""Bank statement parser using table columns as the debit/credit authority."""

import re
from statistics import median
from typing import Any

from fextract.normalize.dates import normalize_date
from fextract.normalize.numbers import normalize_number
from fextract.schemas import FieldValue

DATE = re.compile(r"^\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b")


def _field(value: Any, page: int | None = None, source: str = "rule") -> FieldValue:
    """Wrap one parsed bank metadata value with provenance."""
    return FieldValue(
        value=value,
        confidence=0.8 if value is not None else 0,
        page=page if value is not None else None,
        source=source if value is not None else "none",
        null_reason=None if value is not None else "not_present",
        flags=[] if value is not None else ["review"],
    )


def parse_bank_table_pages(
    page_tables: dict[int, list[list[list[str | None]]]],
    page_ids: list[int],
) -> tuple[dict[str, FieldValue], list[dict[str, Any]]]:
    """Extract bank rows from positioned table columns, preserving page order.

    pdfplumber's table grid is used to map debit, credit, and balance by their
    header columns; amount signs are never used to infer transaction direction.
    """
    rows: list[dict[str, Any]] = []
    for page_id in page_ids:
        for table in page_tables.get(page_id, []):
            header_index = None
            columns: dict[str, int] = {}
            for index, raw_header in enumerate(table[:4]):
                header = [
                    re.sub(r"\W+", " ", str(cell or "").lower()).strip()
                    for cell in raw_header
                ]
                joined = " | ".join(header)
                if "txn date" not in joined and "transaction date" not in joined:
                    continue
                header_index = index
                aliases = {
                    "txn_date": ("txn date", "transaction date"),
                    "value_date": ("value date",),
                    "cheque_no": ("cheque no", "check no"),
                    "description": ("description", "narration", "particulars"),
                    "branch_code": ("branch code",),
                    "debit": ("debit", "withdrawal"),
                    "credit": ("credit", "deposit"),
                    "balance": ("balance",),
                }
                for key, names in aliases.items():
                    for column_index, value in enumerate(header):
                        if any(name in value for name in names):
                            columns[key] = column_index
                            break
                break
            if header_index is None:
                continue

            def cell(cells: list[str | None], key: str) -> str:
                column_index = columns.get(key)
                return (
                    str(cells[column_index] or "").strip()
                    if column_index is not None and column_index < len(cells)
                    else ""
                )

            for cells in table[header_index + 1 :]:
                txn_text = cell(cells, "txn_date")
                txn_match = DATE.match(txn_text)
                description = " ".join(cell(cells, "description").split())
                if not txn_match:
                    if rows and description:
                        rows[-1]["description"] = (
                            rows[-1]["description"] + " " + description
                        ).strip()
                    continue
                debit_result = normalize_number(cell(cells, "debit"))
                credit_result = normalize_number(cell(cells, "credit"))
                balance_result = normalize_number(cell(cells, "balance"))
                rows.append(
                    {
                        "txn_date": normalize_date(txn_match.group(1)),
                        "value_date": normalize_date(cell(cells, "value_date")) or None,
                        "cheque_no": cell(cells, "cheque_no") or None,
                        "description": description,
                        "branch_code": cell(cells, "branch_code") or None,
                        "debit": debit_result.value,
                        "credit": credit_result.value,
                        "balance": balance_result.value,
                        "page": page_id,
                    }
                )
    first, last = (rows[0] if rows else None), (rows[-1] if rows else None)
    opening = None
    if first and first["balance"] is not None:
        opening = (
            float(first["balance"])
            + float(first["debit"] or 0)
            - float(first["credit"] or 0)
        )
    fields = {
        "account_holder": _field(None),
        "account_number": _field(None),
        "period_start": _field(None),
        "period_end": _field(None),
        "opening_balance": _field(
            opening, first["page"] if first and opening is not None else None, "derived"
        ),
        "closing_balance": _field(
            last["balance"] if last else None, last["page"] if last else None, "derived"
        ),
    }
    return fields, rows


def parse_bank_positioned_pages(
    page_words: dict[int, list[dict[str, object]]], page_ids: list[int]
) -> tuple[dict[str, FieldValue], list[dict[str, Any]]]:
    """Parse header-aligned transaction columns by word x-position."""
    rows: list[dict[str, Any]] = []
    columns: dict[str, float] = {}
    period_values: list[str] = []
    aliases = {
        "txn_date": "date",
        "description": "description",
        "debit": "debit",
        "credit": "credit",
        "balance": "balance",
    }
    for page_id in page_ids:
        words = page_words.get(page_id, [])
        ordered_words = sorted(
            words,
            key=lambda word: float(word.get("bottom", word.get("top", 0))),
        )
        heights = [
            float(word.get("bottom", word.get("top", 0))) - float(word.get("top", 0))
            for word in words
            if "bottom" in word
        ]
        line_tolerance = max(12.0, median(heights) * 1.25) if heights else 12.0
        lines: list[tuple[float, list[dict[str, object]]]] = []
        for word in ordered_words:
            baseline = float(word.get("bottom", word.get("top", 0)))
            if not lines or abs(lines[-1][0] - baseline) > line_tolerance:
                lines.append((baseline, [word]))
            else:
                line_y, line_words = lines[-1]
                line_words.append(word)
                lines[-1] = (
                    sum(
                        float(item.get("bottom", item.get("top", 0)))
                        for item in line_words
                    )
                    / len(line_words),
                    line_words,
                )
        for _, line in lines:
            ordered = sorted(line, key=lambda word: float(word.get("x0", 0)))
            tokens = [str(word.get("text", "")).casefold() for word in ordered]
            joined = " ".join(tokens)
            if "statement period" in joined:
                period_values.extend(
                    re.findall(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", joined)
                )
            if (
                "date" in tokens
                and "description" in tokens
                and "balance" in tokens
                and ("debit" in tokens or "credit" in tokens)
            ):
                date_index = tokens.index("date")
                if date_index and tokens[date_index - 1] in {"txn", "transaction"}:
                    date_index -= 1
                columns = {
                    "txn_date": float(ordered[date_index].get("x0", 0)),
                    **{
                        name: float(ordered[tokens.index(alias)].get("x0", 0))
                        for name, alias in aliases.items()
                        if alias != "date" and alias in tokens
                    },
                }
                # OCR can place the header box several pixels to the right
                # of the numbers below it; use a small left tolerance while
                # still routing values by the measured column boundaries.
                for numeric_column in ("debit", "credit", "balance"):
                    if numeric_column in columns:
                        columns[numeric_column] -= 20
                continue
            if not columns:
                continue

            def bucket(name: str) -> str:
                if name not in columns:
                    return ""
                start = columns[name]
                end = min(
                    (x for key, x in columns.items() if x > start),
                    default=float("inf"),
                )
                return " ".join(
                    str(word.get("text", ""))
                    for word in ordered
                    if start <= float(word.get("x0", 0)) < end
                ).strip()

            txn_text = bucket("txn_date")
            txn_match = DATE.match(txn_text)
            if txn_match:
                debit_text, credit_text, balance_text = (
                    bucket("debit"),
                    bucket("credit"),
                    bucket("balance"),
                )
                debit_value = normalize_number(debit_text) if debit_text else None
                credit_value = normalize_number(credit_text) if credit_text else None
                balance_value = normalize_number(balance_text) if balance_text else None
                rows.append(
                    {
                        "txn_date": normalize_date(txn_match.group(1)),
                        "value_date": None,
                        "cheque_no": None,
                        "description": bucket("description"),
                        "branch_code": None,
                        "debit": debit_value.value if debit_value else None,
                        "credit": credit_value.value if credit_value else None,
                        "balance": balance_value.value if balance_value else None,
                        "page": page_id,
                    }
                )
            elif rows:
                continuation = bucket("description")
                if continuation:
                    rows[-1]["description"] = (
                        str(rows[-1]["description"]) + " " + continuation
                    ).strip()
    first = rows[0] if rows else None
    last = rows[-1] if rows else None
    opening = (
        float(first["balance"]) + float(first["debit"]) - float(first["credit"])
        if first
        and first["balance"] is not None
        and first["debit"] is not None
        and first["credit"] is not None
        else None
    )
    start = normalize_date(period_values[0]) if period_values else None
    end = normalize_date(period_values[-1]) if len(period_values) > 1 else start
    fields = {
        "account_holder": _field(None),
        "account_number": _field(None),
        "period_start": _field(start),
        "period_end": _field(end),
        "opening_balance": _field(
            opening, first["page"] if first and opening is not None else None, "derived"
        ),
        "closing_balance": _field(
            last["balance"] if last else None, last["page"] if last else None, "derived"
        ),
    }
    return fields, rows


def parse_bank_statement(
    text: str, page: int = 1
) -> tuple[dict[str, FieldValue], list[dict[str, object]]]:
    """Conservative fallback for plain text without table geometry.

    Transaction amounts remain null because flattening text loses their column
    positions. The pipeline uses :func:`parse_bank_table_pages` for digital PDFs.
    """
    rows: list[dict[str, object]] = []
    for line in text.splitlines():
        match = DATE.match(line)
        if match:
            rows.append(
                {
                    "txn_date": normalize_date(match.group(1)),
                    "value_date": None,
                    "cheque_no": None,
                    "description": line[match.end() :].strip(),
                    "branch_code": None,
                    "debit": None,
                    "credit": None,
                    "balance": None,
                    "page": page,
                }
            )
        elif rows and line.strip():
            rows[-1]["description"] = (
                str(rows[-1]["description"]) + " " + line.strip()
            ).strip()
    fields = {
        "account_holder": _field(None),
        "account_number": _field(None),
        "period_start": _field(None),
        "period_end": _field(None),
        "opening_balance": _field(None),
        "closing_balance": _field(None),
    }
    return fields, rows
