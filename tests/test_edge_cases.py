"""Graceful handling of bad and unknown input."""

from pathlib import Path
import fitz
from fextract.ingest.loader import discover_files
from fextract.pipeline import extract_document


def test_junk_and_unknown_extensions_are_ignored(tmp_path: Path):
    (tmp_path / ".DS_Store").write_text("x")
    (tmp_path / "note.txt").write_text("x")
    accepted, ignored = discover_files(tmp_path)
    assert accepted == [] and len(ignored) == 2


def test_empty_document_returns_error_record(tmp_path: Path):
    source = tmp_path / "empty.pdf"
    source.touch()
    assert extract_document(source).errors


def test_non_finance_recipe_is_unknown_without_extracted_fields(tmp_path: Path):
    source = tmp_path / "recipe.pdf"
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "Recipe: flour, sugar, butter, eggs. Mix and bake.")
    pdf.save(source)
    pdf.close()

    result = extract_document(source)

    assert not result.errors
    assert all(section.doc_type == "unknown" for section in result.sections)
    assert all(not section.fields for section in result.sections)


def test_blank_pdf_page_has_blank_extraction_path(tmp_path: Path):
    source = tmp_path / "blank.pdf"
    pdf = fitz.open()
    pdf.new_page()
    pdf.save(source)
    pdf.close()

    result = extract_document(source)

    assert not result.errors
    assert result.extraction_paths == {1: "blank"}
    assert result.sections[0].doc_type == "unknown"
    assert result.sections[0].fields == {}
