"""Rule parser for cash flow statement totals and activity sections."""

import re
from fextract.normalize.numbers import normalize_number
from fextract.schemas import FieldValue
from fextract.extract.parsers.positioned_finance import find_row_values
from fextract.normalize.units import detect_unit


def parse_cash_flow(text: str, page: int = 1) -> dict[str, FieldValue]:
    """Extract current/prior cash flow totals and unit from labelled lines."""
    lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    patterns = {
        "net_change": r"net (?:increase|decrease|change)(?:/\(decrease\))?.*cash|net change",
        "opening_cash": r"(?:cash.*beginning|opening cash|cash and cash equivalents at beginning)",
        "closing_cash": r"(?:cash.*end|closing cash|cash and cash equivalents at end)",
    }

    def values_near(index: int) -> list[float]:
        values = []
        token_pattern = (
            r"(?<!\w)(\(?-?(?:\d{1,3}(?:,\d{2,3})+|\d+)" r"(?:\.\d+)?\)?-?)(?!\w)"
        )
        for offset, line in enumerate(lines[index : index + 7]):
            if re.search(r"\b(?:refer\s+)?note\b", line, re.I):
                continue
            if (
                offset
                and re.search(r"\bnote\b", lines[index + offset - 1], re.I)
                and re.fullmatch(r"\s*\d{1,2}\s*", line)
            ):
                continue
            for token in re.findall(token_pattern, line):
                value = normalize_number(token).value
                if value is not None:
                    values.append(value)
                    if len(values) == 2:
                        return values
        return values

    found = {}
    for key, label in patterns.items():
        for index, line in enumerate(lines):
            if re.search(label, line, re.I):
                vals = values_near(index)
                if not vals and re.search(label, line, re.I):
                    nums = re.findall(r"\(?-?[\d,]+(?:\.\d+)?\)?-?", line)
                    vals = [normalize_number(x).value for x in nums]
                    vals = [v for v in vals if v is not None]
                if vals:
                    found[key] = vals
                    break
    # Activities are the section totals (A, B, C), typically one per line.
    activities = {}
    for name, activity in (
        ("operating_activities", "operating"),
        ("investing_activities", "investing"),
        ("financing_activities", "financing"),
    ):
        # Annual reports use several equivalent forms, including
        # "(used in) / generated from ... - [A]". Match the activity anchor,
        # not the wording of the cash-flow direction or its note tag.
        label = rf"\bnet\s+cash\b.*\b{activity}\s+activities\b"
        for index, line in enumerate(lines):
            if re.search(label, line, re.I):
                vals = values_near(index)
                if vals:
                    activities[name] = vals
                    break
    fields = {}
    for name in (*patterns, *activities):
        vals = found.get(name, activities.get(name))
        fields[name] = FieldValue(
            value=vals[0] if vals else None,
            confidence=0.8 if vals else 0,
            page=page if vals else None,
            source="rule" if vals else "none",
            null_reason=None if vals else "not_present",
            flags=[] if vals else ["review"],
        )
        if vals and len(vals) > 1:
            fields[name + "_prior_year"] = FieldValue(
                value=vals[1], confidence=0.8, page=page, source="rule"
            )
    unit = detect_unit(text)
    fields["unit"] = (
        FieldValue(value=unit, confidence=0.8, page=page, source="rule")
        if unit
        else FieldValue(null_reason="not_present", flags=["review"])
    )
    return fields


def parse_cash_flow_positioned(
    words_by_page: dict[int, list[dict]],
) -> dict[str, FieldValue]:
    """Extract cash-flow summary lines using detected current/prior columns."""
    patterns = {
        "net_change": r"net (?:increase|decrease)(?:/\(decrease\))?.*cash and cash equivalents",
        "opening_cash": r"cash and cash equivalents at the beginning",
        "closing_cash": r"cash and cash equivalents at the end",
    }
    fields = {}
    for field, pattern in patterns.items():
        values = []
        page = None
        for page_id, words in words_by_page.items():
            values = find_row_values(words, pattern)
            if values:
                page = page_id
                break
        if not values:
            continue
        fields[field] = FieldValue(
            value=values[0], confidence=0.9, page=page, source="rule"
        )
        if len(values) > 1:
            fields[f"{field}_prior_year"] = FieldValue(
                value=values[1], confidence=0.9, page=page, source="rule"
            )
    return fields
