"""Input discovery and defensive document loading."""

from pathlib import Path

SUPPORTED = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}


def discover_files(path: Path) -> tuple[list[Path], list[tuple[Path, str]]]:
    """Return supported files and ignored entries, recursively and stably."""
    candidates = (
        [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file())
    )
    accepted, ignored = [], []
    for candidate in candidates:
        if candidate.name == ".DS_Store" or candidate.name.startswith("~$"):
            ignored.append((candidate, "junk file"))
        elif candidate.suffix.lower() not in SUPPORTED:
            ignored.append((candidate, "unsupported extension"))
        else:
            accepted.append(candidate)
    return accepted, ignored


def load_pdf(path: Path):
    """Open a PDF with PyMuPDF; raise a clear error for invalid or encrypted input."""
    import fitz

    if path.stat().st_size == 0:
        raise ValueError("empty file")
    document = fitz.open(path)
    if document.needs_pass:
        document.close()
        raise ValueError("password-protected PDF")
    if document.page_count == 0:
        document.close()
        raise ValueError("PDF has no pages")
    return document
