"""Rule parser for common profit and loss totals."""

import re
from fextract.normalize.numbers import normalize_number
from fextract.schemas import FieldValue
from fextract.normalize.units import detect_unit
from fextract.extract.parsers.positioned_finance import (
    financial_rows,
    find_row_values,
    row_period_values,
)


def parse_profit_loss(text: str, page: int = 1) -> dict[str, FieldValue]:
    """Extract revenue, expense, and profit lines by labelled row."""
    fields = {}
    unit = detect_unit(text)
    fields["unit"] = (
        FieldValue(value=unit, confidence=0.8, page=page, source="rule")
        if unit
        else FieldValue(null_reason="not_present", flags=["review"])
    )
    lines = text.splitlines()
    definitions = (
        (
            "revenue",
            r"total revenue|revenue(?: from (?:other )?operations)?",
        ),
        ("other_income", r"other income"),
        ("expenses", r"total expenses"),
        ("exceptional_items", r"^\s*exceptional items?\b"),
        ("profit_before_tax", r"profit before tax"),
        ("tax_expense", r"tax expense"),
        (
            "profit",
            r"net profit(?: transfer to capital a/c)?|profit after tax|profit(?:\s*\(loss\))? for the year",
        ),
    )
    # Prefer explicit statement totals over component rows that happen to
    # contain the same label (for example revenue from operations).
    definitions = tuple(sorted(definitions, key=lambda item: item[0] != "revenue"))
    for field, label in definitions:
        parsed = None
        nil_value = False
        candidate_lines = list(enumerate(lines))
        if field == "revenue":
            totals = [
                pair
                for pair in candidate_lines
                if re.search(r"\btotal\s+revenue\b", pair[1], re.I)
            ]
            if totals:
                candidate_lines = totals + [
                    pair for pair in candidate_lines if pair not in totals
                ]
        for index, line in candidate_lines:
            if not re.search(label, line, re.I):
                continue
            # Skip annotation fragments such as (I-II), and only accept an
            # amount on the labelled row or the immediately following row.
            label_match = re.search(label, line, re.I)
            value_tail = line[label_match.end() :] if label_match else line
            nil_match = re.fullmatch(r"\s*[:\-]?\s*(?:-|–|—|nil)\s*", value_tail, re.I)
            if nil_match:
                parsed = normalize_number("0")
                nil_value = True
                break
            # Leading row indices (for example "1 Revenue") and bare note
            # references are not financial amounts. A grouped or decimal
            # value is a stronger inline candidate.
            candidates = re.findall(
                r"(?<!\w)\(?\d[\d,]*(?:\.\d+)?\)?-?(?!\w)", value_tail
            )
            candidates = [
                value
                for value in candidates
                if (
                    "," in value
                    or "." in value
                    or (value.startswith("(") and sum(c.isdigit() for c in value) >= 4)
                )
                and not re.fullmatch(r"\(\s*\d+\s*-\s*\d+\s*\)", value)
            ]
            for candidate in candidates:
                # A scan may drop the closing bracket of a printed negative.
                # Preserve the sign and make the OCR ambiguity visible through
                # the low rule confidence rather than turning it positive.
                if candidate.startswith("(") and not candidate.endswith(")"):
                    normalized = normalize_number(candidate[1:] + "-")
                else:
                    normalized = normalize_number(candidate)
                if normalized.value is not None:
                    parsed = normalized
            if parsed is None:
                for following in lines[index + 1 : index + 5]:
                    if re.search(
                        r"total revenue|total expenses|profit before tax|"
                        r"profit\s*\(loss\)|profit.*for the year|tax expense|"
                        r"current tax|deferred tax|exceptional items?",
                        following,
                        re.I,
                    ):
                        break
                    if re.fullmatch(r"\s*(?:-|–|—|nil)\s*", following, re.I):
                        parsed = normalize_number("0")
                        nil_value = True
                        break
                    adjacent_values = re.findall(
                        r"(?<!\w)\(?\d[\d,]*(?:\.\d+)?\)?-?(?!\w)",
                        following,
                    )
                    adjacent_values = [
                        value
                        for value in adjacent_values
                        if (
                            "," in value
                            or "." in value
                            or sum(character.isdigit() for character in value) >= 4
                            or (
                                value.startswith("(")
                                and sum(c.isdigit() for c in value) >= 4
                            )
                        )
                        and not re.fullmatch(r"\(\s*\d+\s*-\s*\d+\s*\)", value)
                    ]
                    if adjacent_values:
                        parsed = normalize_number(adjacent_values[-1])
                        break
            if parsed is not None and parsed.value is not None:
                break
        value = parsed.value if parsed else None
        fields[field] = FieldValue(
            value=value,
            confidence=0.78 if value is not None else 0,
            page=page if value is not None else None,
            source="rule" if value is not None else "none",
            null_reason=None if value is not None else "not_present",
            flags=["nil"] if nil_value else ([] if value is not None else ["review"]),
        )

    # Resolve omitted statement components only when the printed totals make
    # the residual unambiguous. Keep the derivation explicit in provenance.
    operations_value = None
    for index, line in enumerate(lines):
        label_match = re.search(
            r"revenue\s+from\s+(?:other\s+)?operations\b", line, re.I
        )
        if not label_match:
            continue
        nearby = " ".join([line[label_match.end() :], *lines[index + 1 : index + 5]])
        operation_match = re.search(
            r"(?<!\w)(\(?-?(?:\d{1,3}(?:,\d{2,3})+|\d{4,})(?:\.\d+)?\)?-?)(?!\w)",
            nearby,
        )
        if operation_match:
            operations_value = normalize_number(operation_match.group(1)).value
            break
    if (
        fields["other_income"].value is None
        and operations_value is not None
        and fields["revenue"].value is not None
        and re.search(r"\bother income\b", text, re.I)
    ):
        fields["other_income"] = FieldValue(
            value=float(fields["revenue"].value) - operations_value,
            confidence=0.65,
            page=page,
            source="derived",
            flags=["derived_from_statement_totals"],
        )
    if fields["exceptional_items"].value is None and not re.search(
        r"\bexceptional items?\b", text, re.I
    ):
        fields["exceptional_items"] = FieldValue(
            value=0,
            confidence=0.65,
            page=page,
            source="derived",
            flags=["derived_absent_adjustment_line"],
        )
    if (
        fields["tax_expense"].value is None
        and fields["profit_before_tax"].value is not None
        and fields["profit"].value is not None
        and re.search(r"\btax expense\b", text, re.I)
    ):
        fields["tax_expense"] = FieldValue(
            value=float(fields["profit"].value)
            - float(fields["profit_before_tax"].value),
            confidence=0.65,
            page=page,
            source="derived",
            flags=["derived_from_statement_totals"],
        )
    return fields


def parse_profit_loss_positioned(
    words: list[dict], page: int = 1
) -> dict[str, FieldValue]:
    """Extract P&L values from statement rows and detected period columns."""
    output = {}
    patterns = {
        "revenue": r"(?:revenue from (?:other )?operations|total revenue|revenue)\b",
        "other_income": r"\bother income\b",
        "expenses": r"\btotal expenses\b",
        "exceptional_items": r"^\s*exceptional items?\b",
        "profit_before_tax": r"\bprofit before tax\b",
        "tax_expense": r"\btax expense\b",
        "profit": r"\bprofit(?: \(loss\))? for the year\b|\bprofit after tax\b",
    }
    rows, columns, note_x = financial_rows(words)
    for field, pattern in patterns.items():
        values = find_row_values(words, pattern)
        if not values:
            continue
        matching_row = next(
            (row for row in rows if re.search(pattern, row["text"], re.I)), None
        )
        nil_row = bool(
            matching_row
            and any(
                re.fullmatch(r"[-–—]|nil", str(word.get("text", "")).strip(), re.I)
                for word in matching_row["words"]
            )
        )
        output[field] = FieldValue(
            value=values[0],
            confidence=0.9,
            page=page,
            source="rule",
            flags=["nil"] if nil_row else [],
        )
        if len(values) > 1:
            output[f"{field}_prior_year"] = FieldValue(
                value=values[1],
                confidence=0.9,
                page=page,
                source="rule",
                flags=["nil"] if nil_row else [],
            )

    # Tax rows are commonly shown as signed subcomponents under a label-only
    # "Tax expenses" row. Sum the extracted current and deferred tax lines,
    # preserving their printed signs, rather than treating the first note
    # reference or subrow as the total tax adjustment.
    rows, columns, note_x = financial_rows(words)
    tax_header = next(
        (
            index
            for index, row in enumerate(rows)
            if re.fullmatch(r"tax expenses?", row["text"].strip(), re.I)
        ),
        None,
    )
    if tax_header is not None:
        profit_row = next(
            (
                index
                for index in range(tax_header + 1, len(rows))
                if re.search(r"\bprofit for the year\b", rows[index]["text"], re.I)
            ),
            len(rows),
        )
        tax_rows = [
            row
            for row in rows[tax_header + 1 : profit_row]
            if re.match(
                r"\s*(?:current tax|deferred tax\b|tax for earlier years\b)",
                row["text"],
                re.I,
            )
        ]
        tax_values = [row_period_values(row, columns, note_x) for row in tax_rows]
        if tax_values and all(len(values) == len(columns) for values in tax_values):
            sums = [
                sum(values[column] for values in tax_values)
                for column in range(len(columns))
            ]
            output["tax_expense"] = FieldValue(
                value=sums[0], confidence=0.9, page=page, source="derived"
            )
            if len(sums) > 1:
                output["tax_expense_prior_year"] = FieldValue(
                    value=sums[1], confidence=0.9, page=page, source="derived"
                )
    return output
