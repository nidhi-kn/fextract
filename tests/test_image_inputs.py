"""Synthetic raster-input tests without external OCR model requirements."""

from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from fextract.ocr.base import OCRWord
from fextract.ocr.tesseract_engine import TesseractEngine
from fextract.pipeline import _ocr_words_to_lines, extract_document


def _words(lines: list[str]) -> list[OCRWord]:
    """Create positioned OCR tokens for a fictional statement page."""
    result = []
    for line_number, line in enumerate(lines):
        x = 20
        y = 30 + line_number * 45
        for token in line.split():
            width = max(12, len(token) * 9)
            result.append(OCRWord(token, [x, y, x + width, y + 18], 0.98))
            x += width + 10
    return result


def _image(path: Path) -> None:
    """Render a plain synthetic page as PNG or JPEG."""
    image = Image.new("RGB", (1200, 1600), "white")
    draw = ImageDraw.Draw(image)
    draw.text((30, 30), "Fictional finance document", fill="black")
    image.save(path)


def _finance_image(path: Path, lines: list[str]) -> None:
    """Render large, OCR-readable fictional statement text to a raster file."""
    font_path = next(
        (
            candidate
            for candidate in (
                Path("C:/Windows/Fonts/arial.ttf"),
                Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            )
            if candidate.is_file()
        ),
        None,
    )
    font = (
        ImageFont.truetype(str(font_path), 40)
        if font_path
        else ImageFont.load_default(size=40)
    )
    image = Image.new("RGB", (1800, 1200), "white")
    draw = ImageDraw.Draw(image)
    for index, line in enumerate(lines):
        draw.text((80, 60 + index * 130), line, font=font, fill="black")
    image.save(path, quality=95)


@pytest.mark.parametrize("extension", ["png", "jpg"])
@pytest.mark.parametrize(
    ("kind", "lines", "field", "expected"),
    [
        (
            "invoice",
            [
                "Commercial Invoice",
                "Invoice No FICTION-2026",
                "Invoice Date 04 Jan 2025",
                "Seller Acme Fictional Ltd",
                "Total Sales Value 150.00",
            ],
            "invoice_number",
            "FICTION-2026",
        ),
        (
            "cash-flow",
            [
                "Cash Flow Statement",
                "Net increase in cash and cash equivalents",
                "10",
                "Cash and cash equivalents at the beginning of the year",
                "50",
                "Cash and cash equivalents at the end of the year",
                "60",
            ],
            "net_change",
            10.0,
        ),
    ],
)
def test_image_pipeline_extracts_from_line_preserving_ocr(
    tmp_path: Path, monkeypatch, extension, kind, lines, field, expected
):
    """Raster invoice and cash-flow pages reach their normal rule parsers."""
    path = tmp_path / f"synthetic-{kind}.{extension}"
    _image(path)
    monkeypatch.setattr(TesseractEngine, "run", lambda self, image: _words(lines))

    result = extract_document(path)

    assert not result.errors
    assert result.extraction_paths == {1: "ocr"}
    extracted = [
        section.fields[field].value
        for section in result.sections
        if field in section.fields
    ]
    assert expected in extracted


def test_ocr_words_are_grouped_by_line_and_x_position():
    words = [
        OCRWord("second", [60, 45, 100, 60], 0.9),
        OCRWord("first", [10, 40, 50, 55], 0.9),
        OCRWord("next", [10, 90, 40, 105], 0.9),
    ]

    assert _ocr_words_to_lines(words) == "first second\nnext"


@pytest.mark.parametrize(
    ("extension", "kind", "lines", "field", "expected"),
    [
        (
            "png",
            "invoice",
            [
                "COMMERCIAL INVOICE",
                "Invoice No: FICTION-2026",
                "Invoice Date: 04 Jan 2025",
                "Seller: Acme Fictional Ltd",
                "Total Sales Value: 150.00",
            ],
            "invoice_number",
            "FICTION-2026",
        ),
        (
            "jpg",
            "cash-flow",
            [
                "CASH FLOW STATEMENT",
                "Net increase in cash and cash equivalents",
                "10",
                "Cash and cash equivalents at the beginning of the year",
                "50",
                "Cash and cash equivalents at the end of the year",
                "60",
            ],
            "net_change",
            10.0,
        ),
    ],
)
def test_real_ocr_extracts_known_value_from_synthetic_raster(
    tmp_path: Path, extension, kind, lines, field, expected
):
    """Exercise Tesseract on rendered synthetic invoice/cash-flow page images."""
    path = tmp_path / f"real-ocr-{kind}.{extension}"
    _finance_image(path, lines)

    result = extract_document(path)

    if result.errors:
        assert result.page_count == 0
        assert any(
            "Tesseract" in error or "OCR unavailable" in error
            for error in result.errors
        )
    else:
        assert result.extraction_paths == {1: "ocr"}
        assert any(
            section.fields.get(field) and section.fields[field].value == expected
            for section in result.sections
        )


def test_missing_tesseract_returns_error_record_not_crash(tmp_path: Path, monkeypatch):
    path = tmp_path / "image.jpg"
    _image(path)

    def unavailable(self, image):
        raise RuntimeError("Tesseract unavailable in test environment")

    monkeypatch.setattr(TesseractEngine, "run", unavailable)
    result = extract_document(path)

    assert result.errors
    assert result.sections == []
