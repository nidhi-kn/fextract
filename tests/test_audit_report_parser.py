"""Fictional audit report extraction fixtures."""

from fextract.extract.parsers.audit_report import parse_audit_report


def test_audit_report_reads_members_signature_and_ordinal_dates():
    fields = parse_audit_report(
        "INDEPENDENT AUDITOR'S REPORT\nTHE MEMBERS OF ORCHARD COMPONENTS LTD\n"
        "For NORTHSTAR AUDIT LLP\nChartered Accountants\n"
        "Balance Sheet as at 31st March, 2022\nDate: 6th September,2022"
    )
    assert fields["entity_name"].value == "ORCHARD COMPONENTS LTD"
    assert fields["auditor_firm"].value == "NORTHSTAR AUDIT LLP"
    assert fields["balance_sheet_date"].value == "2022-03-31"
    assert fields["report_date"].value == "2022-09-06"


def test_auditor_letterhead_is_used_instead_of_accounting_institute_phrase():
    fields = parse_audit_report(
        "BLUE OAK AUDIT PARTNERS\nCHARTERED ACCOUNTANTS\n"
        "We follow guidance from the Institute of Chartered Accountants."
    )
    assert fields["auditor_firm"].value == "BLUE OAK AUDIT PARTNERS"


def test_letterhead_firm_trims_line_end_whitespace():
    fields = parse_audit_report("NORTHSTAR AUDIT LLP  \nCHARTERED ACCOUNTANTS")
    assert fields["auditor_firm"].value == "NORTHSTAR AUDIT LLP"
