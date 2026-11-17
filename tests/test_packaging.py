"""Project installation metadata regressions."""

from pathlib import Path


def test_core_dependencies_include_pdfplumber_and_pytesseract():
    project_file = Path(__file__).parents[1] / "pyproject.toml"
    project = project_file.read_text(encoding="utf-8")

    assert '"pdfplumber>=0.11.4"' in project
    assert '"pytesseract>=0.3.13"' in project
