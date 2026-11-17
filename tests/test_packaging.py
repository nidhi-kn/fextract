"""Project installation metadata regressions."""

from pathlib import Path


def test_core_dependencies_are_pinned():
    project_file = Path(__file__).parents[1] / "pyproject.toml"
    project = project_file.read_text(encoding="utf-8")

    expected = [
        '"click==8.3.1"',
        '"pydantic==2.14.2"',
        '"PyMuPDF==1.27.2.2"',
        '"Pillow==13.0.0"',
        '"joblib==1.6.0"',
        '"pdfplumber==0.11.4"',
        '"pytesseract==0.3.13"',
        '"setuptools==84.2.1"',
        '"wheel==0.48.0"',
        '"pytest==9.1.1"',
        '"ruff==0.14.10"',
        '"black==26.1.0"',
    ]

    for dependency in expected:
        assert dependency in project
