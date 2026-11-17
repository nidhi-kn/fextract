"""Dispatch text to document-specific deterministic parsers."""

from fextract.extract.parsers.audit_report import parse_audit_report
from fextract.extract.parsers.balance_sheet import parse_balance_sheet
from fextract.extract.parsers.bank_statement import parse_bank_statement
from fextract.extract.parsers.cash_flow import parse_cash_flow
from fextract.extract.parsers.generic_notes import parse_notes
from fextract.extract.parsers.invoice import parse_invoice
from fextract.extract.parsers.profit_loss import parse_profit_loss


def extract_fields(doc_type: str, text: str, page: int = 1):
    """Extract fields and any structured rows for a classified section."""
    if doc_type == "commercial_invoice":
        return parse_invoice(text, page), {}
    if doc_type == "bank_statement":
        fields, rows = parse_bank_statement(text, page)
        return fields, {"transactions": rows}
    if doc_type == "balance_sheet":
        return parse_balance_sheet(text, page), {}
    if doc_type == "cash_flow_statement":
        return parse_cash_flow(text, page), {}
    if doc_type == "profit_and_loss":
        return parse_profit_loss(text, page), {}
    if doc_type == "audit_report":
        return parse_audit_report(text, page), {}
    if doc_type == "notes_other":
        pairs, table = parse_notes(text)
        return {}, {
            "key_values": [
                {"key": key, "value": value} for key, value in pairs.items()
            ],
            "rows": [{"cells": row} for row in table],
        }
    return {}, {}
