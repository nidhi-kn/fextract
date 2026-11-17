"""End-to-end defensive behavior without requiring external OCR models."""

from pathlib import Path
from fextract.pipeline import extract_document


def test_invalid_pdf_is_error_record(tmp_path: Path):
    source = tmp_path / "broken.pdf"
    source.write_bytes(b"not a pdf")
    result = extract_document(source)
    assert result.errors
    assert result.sections == []


def test_invoice_and_bank_documents_omit_unrelated_cross_section_checks(tmp_path: Path):
    import fitz

    pages = {
        "invoice.pdf": (
            "Commercial Invoice\nInvoice No: FICTION-55\n"
            "Invoice Date: 04 Jan 2025\nTotal Sales Value: 12.00"
        ),
        "bank.pdf": (
            "Bank Statement\nTxn Date Value Date Cheque No Description Debit Credit Balance\n"
            "01/01/2025 01/01/2025 - Opening - - 100.00"
        ),
    }
    for filename, text in pages.items():
        pdf = fitz.open()
        page = pdf.new_page()
        page.insert_text((72, 72), text)
        pdf.save(tmp_path / filename)
        pdf.close()

        result = extract_document(tmp_path / filename)

        assert not result.errors
        assert result.cross_section_validation == []
