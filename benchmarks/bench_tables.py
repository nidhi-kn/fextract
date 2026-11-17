"""Compare table/text extraction tools on the sample PDFs.

Measures, for each tool, wall-clock time and how many expected rows it recovers:
Document2 has 65 invoice line items (rows start with a part number such as A-1016-7626)
and Document6 has 130 bank transactions (rows start with a dd-mm-yyyy date).
Row recovery counts the rows that contain the pattern (capped at the expected count),
so it is an accuracy proxy, not a full cell-level comparison. Run: python benchmarks/bench_tables.py --samples data/samples
"""

import argparse
import csv
import re
import time
from pathlib import Path

CASES = {
    "Document2.pdf": ("invoice line items", re.compile(r"\bA-\d{4}-\d{4}\b"), 65),
    "Document6.pdf": ("bank transactions", re.compile(r"\b\d{2}-\d{2}-\d{4}\b"), 130),
}


def rows_pdfplumber(path):
    import pdfplumber

    rows = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                rows.extend(" ".join(c or "" for c in row) for row in table)
    return rows


def rows_pymupdf(path):
    import fitz

    rows = []
    with fitz.open(path) as doc:
        for page in doc:
            for table in page.find_tables().tables:
                rows.extend(" ".join(c or "" for c in row) for row in table.extract())
    return rows


def rows_camelot(path, flavor):
    import camelot

    rows = []
    for table in camelot.read_pdf(str(path), pages="all", flavor=flavor):
        rows.extend(" ".join(map(str, r)) for r in table.df.values.tolist())
    return rows


def rows_text_lines(path):
    """Plain PyMuPDF text lines, the baseline the project's own parsers start from."""
    import fitz

    with fitz.open(path) as doc:
        return [line for page in doc for line in page.get_text("text").splitlines()]


TOOLS = {
    "pdfplumber.extract_tables": rows_pdfplumber,
    "PyMuPDF.find_tables": rows_pymupdf,
    "Camelot lattice": lambda p: rows_camelot(p, "lattice"),
    "Camelot stream": lambda p: rows_camelot(p, "stream"),
    "PyMuPDF text lines": rows_text_lines,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", default="data/samples")
    parser.add_argument("--output", default="benchmarks/results/tables-comparison.csv")
    args = parser.parse_args()
    out = []
    for filename, (label, pattern, expected) in CASES.items():
        path = Path(args.samples) / filename
        if not path.exists():
            continue
        for tool, fn in TOOLS.items():
            started = time.perf_counter()
            try:
                rows = fn(path)
                error = ""
            except Exception as exc:  # tool missing or failed
                rows, error = [], type(exc).__name__
            seconds = time.perf_counter() - started
            matching = sum(1 for row in rows if pattern.search(row))
            out.append(
                {
                    "file": filename,
                    "target": label,
                    "tool": tool,
                    "expected_rows": expected,
                    "rows_found": matching,
                    "recall": round(min(matching, expected) / expected, 3),
                    "seconds": round(seconds, 2),
                    "error": error,
                }
            )
            print(out[-1])
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(out[0]))
        writer.writeheader()
        writer.writerows(out)


if __name__ == "__main__":
    main()
