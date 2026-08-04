import pymupdf


def is_scanned_pdf(path: str) -> bool:
    """Check if a PDF is scanned (no text layer)."""
    with pymupdf.open(path) as doc:
        for page in doc[:3]:
            if len(page.get_text().strip()) > 50:
                return False
    return True
