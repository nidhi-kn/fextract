"""Cross-section financial reconciliation checks."""

import re
from math import isclose

from fextract.normalize.numbers import normalize_number
from fextract.schemas import SectionResult, ValidationResult
from fextract.extract.parsers.positioned_finance import financial_rows


def _is_numeric_token(word: dict) -> bool:
    """Return whether a positioned token contains a standalone amount."""
    return bool(
        re.fullmatch(r"\(?-?[\d,]+(?:\.\d+)?\)?-?", str(word.get("text", "")).strip())
    )


def _numeric_words(
    words: list[dict], x_min: float, y: float, tolerance: float
) -> list[tuple[float, float]]:
    """Read values near a label while excluding label/reference columns."""
    candidates = []
    for word in words:
        x0, top = float(word["x0"]), float(word["top"])
        raw = str(word.get("text", "")).strip()
        if x0 < x_min or abs(top - y) > tolerance:
            continue
        if not _is_numeric_token(word):
            continue
        number = normalize_number(raw).value
        if number is not None:
            candidates.append((x0, float(number), raw))
    candidates.sort()
    merged = []
    index = 0
    while index < len(candidates):
        x0, value, raw = candidates[index]
        if (
            index + 1 < len(candidates)
            and raw.endswith(".000")
            and candidates[index + 1][2] == "00"
            and candidates[index + 1][0] - (x0 + max(len(raw) * 3, 20)) <= 5
        ):
            joined = raw.replace(".", ",") + ".00"
            value = float(normalize_number(joined).value)
            index += 1
        merged.append((x0, value))
        index += 1
    return [(x, value) for x, value in merged]


def _label_value(
    pages: dict[int, list[dict]], pattern: str, tolerance: float = 15
) -> float | None:
    """Find a numeric value aligned with a labeled row across positioned pages."""
    for words in pages.values():
        ordered = sorted(
            words, key=lambda item: (float(item["top"]), float(item["x0"]))
        )
        for label in ordered:
            if not re.search(pattern, str(label.get("text", "")), re.I):
                continue
            y = float(label["top"])
            x_right = max(
                float(word["x1"])
                for word in ordered
                if abs(float(word["top"]) - y) <= 3
                and float(word["x0"]) >= float(label["x0"])
                and not _is_numeric_token(word)
            )
            values = _numeric_words(words, x_right, y, tolerance)
            if values:
                return values[0][1]
    return None


def _cash_note_total(
    pages: dict[int, list[dict]], page_texts: dict[int, str], note_pages: set[int]
) -> float | None:
    """Find the total row in a note headed with cash and cash equivalents."""
    for page_id, text in page_texts.items():
        if page_id not in note_pages:
            continue
        if not re.search(r"cash and cash (?:equivalents|eaulvalents)", text, re.I):
            continue
        words = pages.get(page_id, [])
        total_words = [
            word
            for word in words
            if str(word.get("text", "")).strip(" :.").casefold() == "total"
        ]
        for label in reversed(total_words):
            y, x = float(label["top"]), float(label["x1"])
            values = _numeric_words(words, x, y, 6)
            if values:
                return values[0][1]
    return None


def _eps_and_weighted_shares(
    page_texts: dict[int, str], pages: dict[int, list[dict]]
) -> tuple[float | None, float | None]:
    """Read EPS from its labeled prose row and weighted shares from positioned row."""
    eps = None
    for text in page_texts.values():
        match = re.search(
            r"(?:earning|earnings) per (?:equity )?share.{0,140}?(\(?-?[\d,]+\.\d+\)?)",
            text,
            re.I | re.S,
        )
        if match:
            eps = normalize_number(match.group(1)).value
            if eps is not None:
                break
    weighted = None
    for words in pages.values():
        ordered = sorted(
            words, key=lambda item: (float(item["top"]), float(item["x0"]))
        )
        for label in ordered:
            if str(label.get("text", "")).casefold() != "weighted":
                continue
            y = float(label["top"])
            row_words = [word for word in ordered if abs(float(word["top"]) - y) <= 5]
            row_text = " ".join(str(word.get("text", "")) for word in row_words)
            if "average" not in row_text:
                continue
            values = _numeric_words(words, float(label["x0"]), y, 3)
            if values:
                weighted = values[-1][1]
                break
        if weighted is not None:
            break
    return (float(eps) if eps is not None else None, weighted)


def _balance_sheet_cash(
    sections: list[SectionResult], positioned_pages: dict[int, list[dict]]
) -> float | None:
    """Find the cash-equivalents row within balance-sheet sections only."""
    page_ids = {
        page
        for section in sections
        if section.doc_type == "balance_sheet"
        for page in section.pages
    }
    for page_id in sorted(page_ids):
        words = positioned_pages.get(page_id, [])
        ordered = sorted(
            words, key=lambda item: (float(item["top"]), float(item["x0"]))
        )
        rows = []
        for word in ordered:
            y = float(word["top"])
            row = next(
                (item for item in reversed(rows) if abs(item["y"] - y) <= 4), None
            )
            if row is None:
                rows.append({"y": y, "words": [word]})
            else:
                row["words"].append(word)
        for row in rows:
            row_text = " ".join(str(word.get("text", "")) for word in row["words"])
            if (
                "cash" not in row_text.casefold()
                or "equivalent" not in row_text.casefold()
            ):
                continue
            right = max(
                float(word["x1"])
                for word in row["words"]
                if not _is_numeric_token(word)
            )
            _, _, note_x = financial_rows(words)
            x_min = max(right, note_x + 20) if note_x is not None else right
            values = _numeric_words(words, x_min, row["y"], 6)
            if values:
                return values[0][1]
    return None


def validate_cross_sections(
    sections: list[SectionResult],
    page_texts: dict[int, str],
    positioned_pages: dict[int, list[dict]],
) -> list[ValidationResult]:
    """Reconcile values across statement and note sections."""
    profit_section = next(
        (
            section
            for section in sections
            if section.doc_type == "profit_and_loss"
            and section.fields.get("profit")
            and section.fields["profit"].value is not None
        ),
        None,
    )
    profit = float(profit_section.fields["profit"].value) if profit_section else None
    profit_unit = (
        str(profit_section.fields["unit"].value).casefold()
        if profit_section
        and profit_section.fields.get("unit")
        and profit_section.fields["unit"].value
        else ""
    )
    if not profit_unit and profit_section:
        statement_text = " ".join(
            page_texts.get(page, "") for page in profit_section.pages
        )
        if re.search(r"\bcrores?\b", statement_text, re.I):
            profit_unit = "crores"
    note_pages = {
        page
        for section in sections
        if section.doc_type == "notes_other"
        for page in section.pages
    }
    note_pages.update(
        page
        for page, text in page_texts.items()
        if re.search(r"\bnotes?\s*(?:no\.?\s*)?0?\d+\b", text, re.I)
    )
    reserve_pages = {
        page: positioned_pages.get(page, [])
        for page in note_pages
        if re.search(
            r"\breserves?\b",
            page_texts.get(page, ""),
            re.I,
        )
    }
    reserve = _label_value(reserve_pages, r"closing")
    bs_cash = _balance_sheet_cash(sections, positioned_pages)
    note_cash = _cash_note_total(positioned_pages, page_texts, note_pages)
    eps, weighted = _eps_and_weighted_shares(page_texts, positioned_pages)

    return [
        ValidationResult(
            check="profit_equals_reserves_closing_balance",
            passed=(
                None
                if profit is None or reserve is None
                else isclose(profit, reserve, abs_tol=0.02)
            ),
            detail=f"profit={profit}, reserves_closing={reserve}",
        ),
        ValidationResult(
            check="eps_equals_profit_over_weighted_shares",
            passed=(
                None
                if profit is None or eps is None or weighted in (None, 0)
                else isclose(
                    round(
                        profit
                        * (10_000_000 if "crore" in profit_unit else 1)
                        / weighted,
                        2,
                    ),
                    float(eps),
                    abs_tol=0.02,
                )
            ),
            detail=f"profit={profit}, eps={eps}, weighted_shares={weighted}",
        ),
        ValidationResult(
            check="cash_note_equals_balance_sheet_cash",
            passed=(
                None
                if note_cash is None or bs_cash is None
                else isclose(note_cash, bs_cash, abs_tol=0.02)
            ),
            detail=f"cash_note={note_cash}, balance_sheet_cash={bs_cash}",
        ),
    ]
