"""Rule parser for audit report identifiers and opinion."""

import re
from fextract.normalize.dates import normalize_date
from fextract.schemas import FieldValue


def _extract_firm(text: str) -> str | None:
    """Extract a named auditor from a signature or firm letterhead."""
    line_suffix = re.search(
        r"(?im)^\s*for\s+(.+?\b(?:LLP|Limited|Ltd\.?|Inc\.?|LLC|PLC))\s*$",
        text,
    )
    if line_suffix:
        candidate = " ".join(line_suffix.group(1).split())
        if not re.search(r"institute of chartered accountants", candidate, re.I):
            return candidate
    letterhead = re.search(
        r"(?im)^\s*([A-Z][A-Z0-9 &.,'-]{2,})\s*\n\s*CHARTERED ACCOUNTANTS\b",
        text,
    )
    if letterhead:
        candidate = " ".join(letterhead.group(1).split())
        if not re.search(r"institute of chartered accountants", candidate, re.I):
            return candidate
    signature = re.search(
        r"(?im)^\s*FOR\s*,\s*([A-Z][A-Z0-9 &.,'-]{2,})\s*$\n\s*CHARTERED ACCOUNTANTS\b",
        text,
    )
    if signature:
        return " ".join(signature.group(1).split())
    return None


def parse_audit_report(text: str, page: int = 1) -> dict[str, FieldValue]:
    """Extract auditor firm, opinion type, entity, and report date if present."""
    fields = {}
    patterns = {
        "entity_name": r"(?:to the members of|the members of|in respect of)\s+([^\n]+)",
        "balance_sheet_date": r"balance sheet as at\s+([^\n]+)",
        "report_date": r"date\s*[:\-]\s*(\d{1,2}(?:st|nd|rd|th)?[\s/-]+[A-Za-z]+,?\s*\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
    }
    opinion = (
        "qualified"
        if re.search(r"qualified opinion|except for", text, re.I)
        else (
            "adverse"
            if re.search(r"adverse opinion", text, re.I)
            else (
                "disclaimer"
                if re.search(r"disclaimer of opinion", text, re.I)
                else (
                    "unmodified"
                    if re.search(r"true and fair|unmodified opinion", text, re.I)
                    else None
                )
            )
        )
    )
    for name, pattern in patterns.items():
        match = re.search(pattern, text, re.I)
        value = match.group(1).strip() if match else None
        if name in {"balance_sheet_date", "report_date"} and value:
            value = normalize_date(value)
        fields[name] = FieldValue(
            value=value,
            confidence=0.72 if value else 0,
            page=page if value else None,
            source="rule" if value else "none",
            null_reason=None if value else "not_present",
            flags=[] if value else ["review"],
        )
    if fields["report_date"].value is None:
        date_matches = re.findall(
            r"\b(\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+\d{4})\b", text
        )
        date_value = normalize_date(date_matches[-1]) if date_matches else None
        fields["report_date"] = FieldValue(
            value=date_value,
            confidence=0.72 if date_value else 0,
            page=page if date_value else None,
            source="rule" if date_value else "none",
            null_reason=None if date_value else "not_present",
            flags=[] if date_value else ["review"],
        )
    firm = _extract_firm(text)
    fields["auditor_firm"] = FieldValue(
        value=firm,
        confidence=0.85 if firm else 0,
        page=page if firm else None,
        source="rule" if firm else "none",
        null_reason=None if firm else "not_present",
        flags=[] if firm else ["review"],
    )
    fields["opinion_type"] = FieldValue(
        value=opinion,
        confidence=0.7 if opinion else 0,
        page=page if opinion else None,
        source="rule" if opinion else "none",
        null_reason=None if opinion else "not_present",
        flags=[] if opinion else ["review"],
    )
    return fields
