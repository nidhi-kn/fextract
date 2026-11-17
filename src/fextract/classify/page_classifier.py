"""Rule-based finance document classification at page granularity."""

from collections.abc import Iterable
import re

KEYWORDS = {
    "commercial_invoice": ("commercial invoice", "invoice no", "total sales value"),
    "bank_statement": (
        "txn date",
        "value date",
        "cheque no",
        "debit",
        "credit",
        "balance",
    ),
    "balance_sheet": ("balance sheet", "assets", "liabilities"),
    "profit_and_loss": (
        "profit and loss",
        "profit before tax",
        "revenue from operations",
    ),
    "cash_flow_statement": ("cash flow statement", "cash flow from", "cash flows"),
    "audit_report": ("independent auditor", "auditor's report", "basis for opinion"),
    "notes_other": (
        "notes to the financial statements",
        "notes on financial statements",
        "notes forming part",
    ),
}

_FINANCE_SIGNAL = re.compile(
    r"\b(?:commercial invoice|invoice no\.?|tax invoice|vat no\.?|eori|"
    r"bank statement|account number|account holder|txn date|transaction date|"
    r"debit|credit|balance sheet|total assets|total liabilities|equity and liabilities|"
    r"share capital|reserves and surplus|revenue|turnover|income|expenses|profit|loss|"
    r"cash flow|cash and cash equivalents|auditor|audit report|financial statements|"
    r"notes to the financial statements)\b",
    re.I,
)


def has_finance_signal(text: str) -> bool:
    """Return whether page text contains a recognized finance-domain phrase."""
    return bool(_FINANCE_SIGNAL.search(text))


def classify_page(text: str) -> tuple[str, float]:
    """Classify a page from headings and table structure, not incidental mentions.

    Note-page headings are checked before statement phrases because notes often
    refer to the balance sheet and statement of profit and loss in their prose.
    """
    lines = [
        " ".join(line.lower().split()) for line in text.splitlines() if line.strip()
    ]
    lowered = " ".join(lines)
    first_lines = " ".join(lines[:20])

    if re.search(r"\b(?:commercial\s+invoice|invoice\s+no\s*[:#])", lowered):
        return "commercial_invoice", 0.99
    if (
        "bank statement" in first_lines
        and re.search(r"\btxn\s+date\b", first_lines)
        and "balance" in first_lines
        and ("debit" in first_lines or "credit" in first_lines)
    ):
        return "bank_statement", 0.94
    if re.search(r"\b(?:txn\s+date|transaction\s+date)\b", first_lines) and all(
        token in first_lines for token in ("debit", "credit", "balance")
    ):
        return "bank_statement", 0.99

    if any(
        re.fullmatch(r"independent auditor['’]s report", line) for line in lines[:30]
    ):
        return "audit_report", 0.99

    if re.search(
        r"\bnotes?\s+(?:to|on|forming part of)\s+(?:the )?financial statements\b",
        first_lines,
    ):
        return "notes_other", 0.97
    if re.search(r"\bnote\s+\d+\s*:", first_lines):
        return "notes_other", 0.94
    if re.search(r"^notes?\s+\d+(?:\s|$)", first_lines):
        return "notes_other", 0.94
    if re.search(r"\bnet profit transfer to (?:the )?capital a/?c\b", lowered):
        # Proprietor trading accounts transfer net profit directly into
        # capital; keep this supporting schedule with generic account content.
        return "notes_other", 0.95
    if (
        re.search(r"\bby\s+balance\s+b/?d\b", lowered)
        and re.search(r"\bto\s+balance\s+c/?f\b", lowered)
        and re.search(r"\bdrawings\b|net\s+profit\s+transfer", lowered)
    ):
        # Capital-account schedules support equity balances but are not a
        # separate primary-statement type in the declared output taxonomy.
        return "notes_other", 0.95
    if re.search(r"\bstatement of changes in equity\b", first_lines):
        # This supported type set has no equity-changes value; preserve it as
        # generic financial-statement content rather than mislabeling it P&L.
        return "notes_other", 0.92

    if re.search(
        r"\b(?:annexure\s+[a-z].*auditor|independent auditor|auditor['’]s report|basis for opinion|in our opinion|management['’]s responsibility for the financial statements|auditor['’]s responsibility|responsibilities for audit of financial statements|report on the internal financial controls)\b",
        first_lines,
    ):
        return "audit_report", 0.96
    if re.search(
        r"\b(?:cash flow statement|statement of cash flows|cash flow from (?:operating|investing|financing) activities)\b",
        first_lines,
    ):
        return "cash_flow_statement", 0.98

    if re.search(r"\bbalance sheet(?:\s*\(contd\.\))?\b", first_lines):
        return "balance_sheet", 0.96

    if any(
        re.fullmatch(r"statement of profit and loss(?: for the year ended .+)?", line)
        for line in lines
    ):
        return "profit_and_loss", 0.99

    # Match a standalone statement heading anywhere on the page. Restricting
    # to a whole line avoids triggering on accounting-policy prose in notes.
    if any(
        re.fullmatch(
            r"(?:statement of )?profit and loss(?: account)?(?: for the year)?",
            line,
        )
        for line in lines
    ):
        return "profit_and_loss", 0.97

    # Some annual reports put a P&L table under INCOME without repeating its
    # title. Require several structural signals and exclude note pages above.
    if (
        "revenue from operations" in first_lines
        and "income" in first_lines
        and ("expenses" in lowered or "total expenses" in lowered)
        and re.search(r"year ended|year ending", first_lines)
    ):
        return "profit_and_loss", 0.92
    p_and_l_signals = sum(
        bool(re.search(pattern, first_lines))
        for pattern in (
            r"\brevenue from (?:other )?operations\b",
            r"\btotal expenses\b",
            r"\bprofit before tax\b",
            r"\bprofit\s*\(loss\)\s*for the year\b",
        )
    )
    if p_and_l_signals >= 2:
        return "profit_and_loss", 0.93
    if (
        "gross receipts" in first_lines
        and "opening stock" in first_lines
        and ("direct purchase" in first_lines or "net profit" in lowered)
    ):
        return "profit_and_loss", 0.92

    scores = {
        label: sum(phrase in lowered for phrase in phrases)
        for label, phrases in KEYWORDS.items()
    }
    balance_sheet_signals = (
        r"\bequity and liabilities\b",
        r"\bshareholders['’]? funds\b",
        r"\bshare capital\b",
        r"\breserves and surplus\b",
        r"\bcapital account\b",
        r"\b(?:current|non.?current) assets\b",
        r"\bfixed assets\b",
        r"\btotal assets\b",
        r"\btotal (?:equity and )?liabilities\b",
    )
    if (
        sum(bool(re.search(pattern, lowered)) for pattern in balance_sheet_signals) >= 2
        and re.search(r"\bassets\b", lowered)
        and re.search(r"\bliab\w*", lowered)
    ):
        return "balance_sheet", 0.92
    if scores["cash_flow_statement"] >= 2:
        return "cash_flow_statement", 0.78
    if scores["notes_other"]:
        return "notes_other", 0.75
    if len(lowered) > 100:
        return "notes_other", 0.35
    return "unknown", 0.0


def classify_pages(texts: Iterable[str]) -> list[tuple[str, float]]:
    """Classify every input page independently."""
    return [classify_page(text) for text in texts]


def classify_page_sources(texts: Iterable[str]) -> tuple[str, float]:
    """Choose the strongest page label across embedded text and fresh OCR."""
    candidates = [classify_page(text) for text in texts if text.strip()]
    return max(candidates, key=lambda result: result[1], default=("unknown", 0.0))
