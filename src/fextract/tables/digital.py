"""Digital PDF table extraction via pdfplumber when available."""


def extract_page_tables(pdf_path: str, page_index: int) -> list[list[list[str]]]:
    """Extract tables from one zero-based PDF page; return empty if unavailable."""
    try:
        import pdfplumber
    except ImportError:
        return []
    with pdfplumber.open(pdf_path) as pdf:
        if page_index >= len(pdf.pages):
            return []
        return [
            table for table in (pdf.pages[page_index].extract_tables() or []) if table
        ]


def extract_page_words(pdf_path: str, page_index: int) -> list[dict[str, object]]:
    """Return positioned digital words for layout parsers such as bank statements."""
    try:
        import pdfplumber
    except ImportError:
        return []
    with pdfplumber.open(pdf_path) as pdf:
        if page_index < 0 or page_index >= len(pdf.pages):
            return []
        return list(pdf.pages[page_index].extract_words())
