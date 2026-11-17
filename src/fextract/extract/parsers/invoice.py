"""Rule parser for commercial invoice header fields."""

import re
from fextract.normalize.dates import normalize_date
from fextract.normalize.numbers import normalize_number
from fextract.schemas import FieldValue

_VENDOR_LABEL = r"(?:consignor|seller|vendor|supplier|from)"
_CUSTOMER_LABEL = r"(?:consignee|buyer|customer|bill\s*to|ship\s*to|sold\s*to)"
_PARTY_LABEL = rf"(?:{_VENDOR_LABEL}|{_CUSTOMER_LABEL})"


def _clean_party(value: str | None) -> str | None:
    """Clean a party label value without imposing vendor-specific names."""
    if value is None:
        return None
    cleaned = " ".join(value.strip(" \t:;,-.\ufffd\u00b0").split())
    return cleaned or None


def _extract_labeled_party(lines: list[str], label_pattern: str) -> str | None:
    """Read a same-line party label or a value on the following line."""
    labels = re.compile(
        rf"^\s*(?P<label>{label_pattern})\s*(?::|;|[-–])\s*(?P<value>.*?)\s*$",
        re.I,
    )
    standalone = re.compile(rf"^\s*(?:{label_pattern})\s*:?\s*$", re.I)
    metadata = re.compile(
        r"^(?:invoice|commercial invoice|tax invoice|invoice no|invoice date|date|currency|tel|telephone|fax|e-?mail|web|website)\b",
        re.I,
    )
    for index, line in enumerate(lines):
        match = labels.match(line)
        if match and match.group("value"):
            value = _clean_party(match.group("value"))
            if value and not metadata.match(value):
                return value
        if standalone.match(line) and index + 1 < len(lines):
            candidate = _clean_party(lines[index + 1])
            if (
                candidate
                and not re.fullmatch(_PARTY_LABEL, candidate, re.I)
                and not re.fullmatch(r"delivery\s+address", candidate, re.I)
                and not metadata.match(candidate)
            ):
                return candidate
    return None


def _letterhead_vendor(lines: list[str]) -> str | None:
    """Find a likely organization name in the opening letterhead lines."""
    legal_suffix = re.compile(
        r"\b(?:limited|ltd\.?|llc|inc\.?|incorporated|corp\.?|corporation|company|co\.?|gmbh|plc|pte\.?|sarl|s\.a\.)\s*$",
        re.I,
    )
    metadata = re.compile(
        r"^(?:invoice|commercial invoice|tax invoice|invoice no|invoice date|date|tel|telephone|fax|e-?mail|web|website|eori|vat|currency)\b",
        re.I,
    )
    for line in lines[:24]:
        candidate = _clean_party(line)
        if not candidate or len(candidate) > 100 or metadata.match(candidate):
            continue
        if (
            legal_suffix.search(candidate)
            and sum(char.isalpha() for char in candidate) >= 4
        ):
            return candidate
    return None


def parse_invoice(text: str, page: int = 1) -> dict[str, FieldValue]:
    """Extract invoice identifiers and party names from labels or letterhead."""
    patterns = {
        "invoice_number": r"(?:invoice\s*(?:no\.?|number|#))\s*[:#-]?\s*([A-Z0-9/-]+)",
        "invoice_date": r"(?:invoice\s*date|dated|date)\s*[:#-]?\s*(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        "incoterm": r"\b(EXW|FCA|CPT|CIP|DAP|DPU|DDP|FOB|CFR|CIF)\b",
    }
    lines = text.splitlines()
    fields = {}
    for name, pattern in patterns.items():
        match = re.search(pattern, text, re.I)
        value = (
            normalize_date(match.group(1))
            if name == "invoice_date" and match
            else match.group(1).strip() if match else None
        )
        fields[name] = FieldValue(
            value=value,
            confidence=0.78 if value else 0,
            page=page if value else None,
            source="rule" if value else "none",
            null_reason=None if value else "not_present",
            flags=[] if value else ["review"],
        )
    parties = {
        "vendor_name": _extract_labeled_party(lines, _VENDOR_LABEL)
        or _letterhead_vendor(lines),
        "customer_name": _extract_labeled_party(lines, _CUSTOMER_LABEL),
    }
    for name, value in parties.items():
        fields[name] = FieldValue(
            value=value,
            confidence=0.82 if value else 0,
            page=page if value else None,
            source="rule" if value else "none",
            null_reason=None if value else "not_present",
            flags=[] if value else ["review"],
        )
    total = re.search(
        r"(?:grand\s+total|invoice\s+total|total\s+sales\s+value)\s*[: ]\s*([^\n]+)",
        text,
        re.I,
    )
    parsed = normalize_number(total.group(1)) if total else None
    fields["total_sales_value"] = FieldValue(
        value=parsed.value if parsed else None,
        confidence=0.78 if parsed and parsed.value is not None else 0,
        page=page if parsed and parsed.value is not None else None,
        source="rule" if parsed and parsed.value is not None else "none",
        null_reason=None if parsed and parsed.value is not None else "not_present",
        flags=[] if parsed and parsed.value is not None else ["review"],
    )
    currency = parsed.currency if parsed else None
    fields["currency"] = (
        FieldValue(value=currency, confidence=0.78, page=page, source="rule")
        if currency
        else FieldValue(null_reason="not_present", flags=["review"])
    )

    def put(name, value, source="rule"):
        fields[name] = FieldValue(
            value=value,
            confidence=0.82 if value is not None else 0,
            page=page if value is not None else None,
            source=source if value is not None else "none",
            null_reason=None if value is not None else "not_present",
            flags=[] if value is not None else ["review"],
        )

    for name, pattern in (
        ("currency", r"Currency\s*[: ]\s*([A-Z]{3})"),
        ("customer_number", r"Cust(?:omer)?\s*No\.?\s*[: ]\s*(\d+)"),
        ("vat_no", r"VAT\s*(?:No\.?|Number)\s*[: ]\s*([A-Z]{2}\s*[\d-]+)"),
        ("eori_no", r"EORI\s*(?:No\.?|Number)?\s*[: ]\s*([A-Z]{2}\s*[\d-]+)"),
        ("freight_value", r"Freight(?:\s+Value)?\s*[: ]\s*([\d,.]+)"),
        ("total_net_weight", r"Total\s+Net\s+Weight\s*[: ]\s*([\d,.]+)"),
    ):
        m = re.search(pattern, text, re.I)
        if m:
            raw = m.group(1)
            parsed = (
                normalize_number(raw)
                if name in {"freight_value", "total_net_weight"}
                else None
            )
            put(name, parsed.value if parsed else raw)
    for name, pattern in (
        ("freight_value", r"([\d,.]+)\s*\n\s*Freight Value"),
        ("total_net_weight", r"([\d,.]+)\s*\n\s*Total Net Weight"),
    ):
        if name not in fields or fields[name].value is None:
            m = re.search(pattern, text, re.I)
            if m:
                put(name, normalize_number(m.group(1)).value)
    return fields


def merge_positioned_party_fallbacks(
    fields: dict[str, FieldValue], positioned_values: dict[str, str], page: int
) -> dict[str, FieldValue]:
    """Use positioned party names only when text rules did not find a value."""
    merged = dict(fields)
    for name, value in positioned_values.items():
        existing = merged.get(name)
        if name in {"vendor_name", "customer_name"} and existing is not None:
            if existing.value is not None:
                continue
        merged[name] = FieldValue(
            value=value,
            confidence=0.9,
            page=page,
            source="rule",
        )
    return merged


def _invoice_column_lines(words: list[dict]) -> dict[str, list[str]]:
    """Extract party columns using role headings, whitespace, and row density."""
    role_tokens = {
        "consignor_address": {"consignor", "seller", "vendor", "supplier"},
        "consignee_address": {"consignee", "buyer", "customer", "bill", "ship", "sold"},
        "delivery_address": {"delivery"},
    }
    headings = {}
    for word in sorted(words, key=lambda item: (float(item["top"]), float(item["x0"]))):
        token = str(word.get("text", "")).casefold().strip(" :;,. ")
        for field, aliases in role_tokens.items():
            if token in aliases and field not in headings:
                headings[field] = (float(word["x0"]), float(word["top"]))
    # A lone role-like token may be part of a party name (for example,
    # "Example Supplier") rather than a column heading. Address blocks need
    # corroborating spatial structure before words are assigned to columns.
    if len(headings) < 2:
        return {}

    rows: dict[int, list[dict]] = {}
    for word in words:
        rows.setdefault(round(float(word["top"]) / 3) * 3, []).append(word)
    first_heading_y = min(y for _, y in headings.values())
    page_width = max(float(word["x1"]) for word in words)
    table_top = min(
        (
            float(row_words[0]["top"])
            for row_words in rows.values()
            if float(row_words[0]["top"]) > first_heading_y + 80
            and len(row_words) >= 8
            and max(float(word["x1"]) for word in row_words)
            - min(float(word["x0"]) for word in row_words)
            >= page_width * 0.65
        ),
        default=first_heading_y + 160,
    )

    by_x = sorted(headings.items(), key=lambda item: item[1][0])

    def rightmost_before(limit: float, start_y: float) -> float:
        return max(
            (
                float(word["x1"])
                for word in words
                if float(word["x0"]) < limit - 2
                and start_y < float(word["top"]) < table_top
            ),
            default=limit - 20,
        )

    bands = {}
    for index, (field, (x0, y)) in enumerate(by_x):
        left = float("-inf")
        right = float("inf")
        if index:
            previous_field, (previous_x, previous_y) = by_x[index - 1]
            left = (rightmost_before(x0, previous_y) + x0) / 2
        if index + 1 < len(by_x):
            next_field, (next_x, _) = by_x[index + 1]
            right = (rightmost_before(next_x, y) + next_x) / 2
        bands[field] = (left, right, y)

    result = {}
    for field, (xmin, xmax, heading_y) in bands.items():
        line_rows: dict[int, list[dict]] = {}
        for word in words:
            x0, top = float(word["x0"]), float(word["top"])
            if x0 < xmin or x0 >= xmax or top <= heading_y or top >= table_top:
                continue
            line_rows.setdefault(round(top / 3) * 3, []).append(word)
        lines = []
        for row_words in (line_rows[key] for key in sorted(line_rows)):
            ordered = sorted(row_words, key=lambda word: float(word["x0"]))
            line = " ".join(str(word["text"]) for word in ordered)
            if re.search(
                r"\b(?:tel|fax|e-mail|email|currency|cust\s*no)\b", line, re.I
            ):
                break
            lines.append(line)
        cleaned = [" ".join(line.split()) for line in lines if line.strip()]
        if cleaned:
            result[field] = cleaned
    return result


def parse_invoice_address_words(words: list[dict]) -> dict[str, str]:
    """Separate invoice party address blocks by role headings and x-position."""
    return {
        field: " ".join(lines) for field, lines in _invoice_column_lines(words).items()
    }


def parse_invoice_party_words(words: list[dict]) -> dict[str, str]:
    """Read vendor and customer names from the first row of their layout blocks."""
    columns = _invoice_column_lines(words)
    result = {}
    for field, address_field in (
        ("vendor_name", "consignor_address"),
        ("customer_name", "consignee_address"),
    ):
        lines = columns.get(address_field, [])
        if lines:
            result[field] = lines[0]
    return result


def parse_invoice_addresses(pdf_path: str, page: int = 0) -> dict[str, str]:
    """Read invoice address columns from positioned digital PDF words."""
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        if page < 0 or page >= len(pdf.pages):
            return {}
        words = pdf.pages[page].extract_words()
    return parse_invoice_address_words(words)


def parse_invoice_items(page_tables, page_ids):
    """Parse invoice item rows across all pages using arithmetic as a signal."""
    rows = []
    for page in page_ids:
        for table in page_tables.get(page, []):
            for cells in table:
                raw = " ".join(str(c or "") for c in cells).replace("\n", " ")
                match = re.search(
                    r"(\d{4}-\d{3})\s+(K[\w/]+)\s+([A-Z0-9][A-Z0-9./-]{3,})\s+(.*)",
                    raw,
                )
                if not match:
                    continue
                prefix = raw[: match.start()].strip()
                body = raw[match.start(4) :].split("Country of Origin:")[0]
                nums = list(
                    re.finditer(
                        r"(?<![A-Za-z0-9])\d[\d,]*(?:\.\d+)?(?![A-Za-z0-9])", body
                    )
                )
                if len(nums) < 4:
                    continue
                selected = None
                for start in range(len(nums) - 3):
                    candidate = nums[start : start + 4]
                    vals_try = [normalize_number(m.group()).value for m in candidate]
                    if any(value is None for value in vals_try):
                        continue
                    if (
                        abs(vals_try[0] * vals_try[1] - vals_try[2]) <= 0.02
                        and abs(vals_try[2] - vals_try[3]) <= 0.02
                    ):
                        selected = candidate
                selected = selected or nums[-4:]
                vals = [normalize_number(m.group()).value for m in selected]
                desc = (
                    body[: selected[0].start()] + " " + body[selected[-1].end() :]
                ).strip()
                desc = " ".join(desc.split())
                origin = re.search(
                    r"Country of Origin:\s*(.*?)(?=Commodity Code|Export CPC|$)",
                    raw,
                    re.I,
                )
                commodity = re.search(r"Commodity Code\s*([\d]+)", raw, re.I)
                rows.append(
                    {
                        "carton": match.group(1) or prefix or None,
                        "order_no": match.group(2),
                        "part_number": match.group(3),
                        "description": desc,
                        "unit_price": vals[0],
                        "qty": vals[1],
                        "sales_value": vals[2],
                        "customs_value": vals[3],
                        "country_of_origin": (
                            origin.group(1).strip() if origin else None
                        ),
                        "commodity_code": commodity.group(1) if commodity else None,
                    }
                )
    return rows
