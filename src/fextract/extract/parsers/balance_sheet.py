"""Rule parser for balance sheet headings, dates, and totals."""

import re
from fextract.normalize.numbers import normalize_number
from fextract.normalize.dates import normalize_date
from fextract.schemas import FieldValue
from fextract.normalize.units import detect_unit


def parse_balance_sheet(text: str, page: int = 1) -> dict[str, FieldValue]:
    """Extract common balance sheet identity and total values conservatively."""
    fields = {}
    entity = re.search(
        r"(?:name of (?:the )?entity|entity|proprietor|properitor)\s*[:\-]?\s*([^\n]+)",
        text,
        re.I,
    )
    fields["entity_name"] = FieldValue(
        value=entity.group(1).strip() if entity else None,
        confidence=0.75 if entity else 0,
        page=page if entity else None,
        source="rule" if entity else "none",
        null_reason=None if entity else "not_present",
        flags=[] if entity else ["review"],
    )
    for name, pattern in (
        ("proprietor", r"(?:proprietor|properitor)\s*[:\-]?\s*([^\n]+)"),
        ("PAN", r"\bPAN(?:\s*NO)?\s*[:\-]?\s*([A-Z]{5}\d{4}[A-Z])"),
        (
            "as_on_date",
            r"as\s+(?:on|at)\s+(\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+\d{4}|\d{1,2}[./-]\d{1,2}[./-]\d{2,4})",
        ),
    ):
        match = re.search(pattern, text, re.I)
        fields[name] = FieldValue(
            value=(
                (
                    normalize_date(match.group(1))
                    if name == "as_on_date"
                    else match.group(1).strip()
                )
                if match
                else None
            ),
            confidence=0.8 if match else 0,
            page=page if match else None,
            source="rule" if match else "none",
            null_reason=None if match else "not_present",
            flags=[] if match else ["review"],
        )
    for name, label in (
        ("total_assets", "total assets"),
        (
            "total_liabilities",
            r"total\s+(?:equity\s+and\s+)?liabilities",
        ),
    ):
        match = re.search(label + r"\s*[:\s]+([()\d,.-]+)", text, re.I)
        number = normalize_number(match.group(1)) if match else None
        val = number.value if number else None
        fields[name] = FieldValue(
            value=val,
            confidence=0.78 if val is not None else 0,
            page=page if val is not None else None,
            source="rule" if val is not None else "none",
            null_reason=None if val is not None else "not_present",
            flags=[] if val is not None else ["review"],
        )
    # Some Indian sole-proprietor balance sheets print two adjacent TOTAL cells
    # rather than separate "total assets/liabilities" labels.
    if (
        fields["total_assets"].value is None
        or fields["total_liabilities"].value is None
    ):
        matches = re.findall(r"\bTOTAL\b\s*([\d,]+(?:\.\d+)?)", text, re.I)
        if len(matches) < 2 and len(re.findall(r"\bTOTAL\b", text, re.I)) >= 2:
            # Some PDF text layers serialize labels before the numeric columns.
            # Use the final two values before the auditor/signature block, which
            # is the printed pair of statement totals in that layout.
            statement = re.split(
                r"\b(?:in terms of our attached report|auditor['’]?s report)\b",
                text,
                flags=re.I,
                maxsplit=1,
            )[0]
            numeric_rows = re.findall(
                r"(?<![A-Za-z])\(?\d[\d,]*(?:\.\d+)?\)?-?(?![A-Za-z])",
                statement,
            )
            matches = numeric_rows[-2:]
        values = [normalize_number(x).value for x in matches]
        values = [x for x in values if x is not None]
        if values:
            for name, value in (
                ("total_liabilities", values[0]),
                ("total_assets", values[-1]),
            ):
                fields[name] = FieldValue(
                    value=value, confidence=0.8, page=page, source="rule"
                )
    unit = detect_unit(text)
    fields["unit"] = (
        FieldValue(value=unit, confidence=0.8, page=page, source="rule")
        if unit
        else FieldValue(null_reason="not_present", flags=["review"])
    )
    assessment = re.search(r"Assessment Year\s*:?\s*(\d{4}-\d{2,4})", text, re.I)
    fields["assessment_year"] = FieldValue(
        value=assessment.group(1) if assessment else None,
        confidence=0.8 if assessment else 0,
        page=page if assessment else None,
        source="rule" if assessment else "none",
        null_reason=None if assessment else "not_present",
        flags=[] if assessment else ["review"],
    )
    previous = re.search(r"Previous Year\s*:?\s*(\d{4}-\d{2,4})", text, re.I)
    fields["financial_year"] = FieldValue(
        value=previous.group(1) if previous else None,
        confidence=0.8 if previous else 0,
        page=page if previous else None,
        source="rule" if previous else "none",
        null_reason=None if previous else "not_present",
        flags=[] if previous else ["review"],
    )
    return fields


def parse_balance_sheet_totals_words(
    words: list[dict], page: int = 1
) -> dict[str, FieldValue]:
    """Read statement totals from positioned words and the nearest section heading."""
    ordered = sorted(words, key=lambda word: (float(word["top"]), float(word["x0"])))
    totals = {}
    current_side = None
    for word in ordered:
        token = str(word.get("text", "")).strip(" :.,").casefold()
        if token in {"liabilities", "liability"}:
            current_side = "total_liabilities"
        elif token == "assets":
            current_side = "total_assets"
        elif token == "total" and current_side:
            y = float(word["top"])
            candidates = [
                candidate
                for candidate in ordered
                if abs(float(candidate["top"]) - y) <= 5
                and float(candidate["x0"]) >= float(word["x0"])
            ]
            numeric = [
                candidate
                for candidate in candidates
                if re.fullmatch(
                    r"\(?-?[\d,]+(?:\.\d+)?\)?-?", str(candidate.get("text", ""))
                )
            ]
            if numeric:
                number = normalize_number(numeric[0]["text"])
                if number.value is not None:
                    totals[current_side] = FieldValue(
                        value=number.value,
                        confidence=0.9,
                        page=page,
                        source="rule",
                    )
    return totals
