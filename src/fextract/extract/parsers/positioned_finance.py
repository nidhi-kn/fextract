"""Helpers for associating finance row labels with period columns."""

from __future__ import annotations

import re

from fextract.normalize.numbers import normalize_number


def financial_rows(words: list[dict]) -> tuple[list[dict], list[float], float | None]:
    """Group positioned words into rows and find current/prior period columns."""
    ordered = sorted(words, key=lambda item: (float(item["top"]), float(item["x0"])))
    rows: list[dict] = []
    for word in ordered:
        y = float(word["top"])
        row = next((item for item in reversed(rows) if abs(item["y"] - y) <= 3), None)
        if row is None:
            rows.append({"y": y, "words": [word]})
        else:
            row["words"].append(word)
    for row in rows:
        row["words"].sort(key=lambda item: float(item["x0"]))
        row["text"] = " ".join(str(item.get("text", "")) for item in row["words"])

    year_pairs = []
    for row in rows:
        years = [
            word
            for word in row["words"]
            if re.fullmatch(r"20\d{2}", str(word.get("text", "")))
        ]
        if len(years) >= 2:
            year_pairs.append((row["y"], years[-2:]))
    period_columns = (
        sorted(
            float(word["x0"]) for word in min(year_pairs, key=lambda pair: pair[0])[1]
        )
        if year_pairs
        else []
    )

    note_x = next(
        (
            float(word["x0"])
            for word in ordered
            if str(word.get("text", "")).strip(" :.").casefold() == "note"
        ),
        None,
    )
    return rows, period_columns, note_x


def row_period_values(
    row: dict, columns: list[float], note_x: float | None
) -> list[float]:
    """Return numeric values, treating explicit nil markers as zero by period."""
    if not columns:
        return []
    numeric = []
    nils = []
    note_boundary = (
        (note_x + columns[0]) / 2
        if note_x is not None and note_x < columns[0]
        else None
    )
    for word in row["words"]:
        raw = str(word.get("text", "")).strip()
        if re.fullmatch(r"[-–—]|nil", raw, re.I):
            nils.append((float(word["x0"]), 0.0))
            continue
        if not re.fullmatch(r"\(?-?[\d,]+(?:\.\d+)?\)?-?", raw):
            continue
        x0 = float(word["x0"])
        if note_boundary is not None and x0 < note_boundary:
            continue
        value = normalize_number(raw).value
        if value is not None:
            numeric.append((x0, value))
    numeric.extend(nils)
    selected = []
    for column in columns:
        if numeric:
            nearest = min(numeric, key=lambda item: abs(item[0] - column))
            selected.append(nearest[1])
            numeric.remove(nearest)
    return selected


def find_row_values(words: list[dict], label_pattern: str) -> list[float]:
    """Find period values on a row matching a statement label."""
    rows, columns, note_x = financial_rows(words)
    for row in rows:
        if re.search(label_pattern, row["text"], re.I):
            values = row_period_values(row, columns, note_x)
            if values:
                return values
    return []
