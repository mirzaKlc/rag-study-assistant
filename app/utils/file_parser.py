"""
File parsing utilities for PDF and TXT documents.

Each parser returns the raw extracted text. Callers are responsible for
chunking and embedding — parsers do only one thing: extract text.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def parse_txt(file_bytes: bytes, encoding: str = "utf-8") -> str:
    """
    Decode a plain-text file to a Python string.

    Falls back to latin-1 when UTF-8 decoding fails, which covers the
    vast majority of real-world text files.
    """
    try:
        return file_bytes.decode(encoding)
    except UnicodeDecodeError:
        logger.warning("UTF-8 decoding failed; falling back to latin-1.")
        return file_bytes.decode("latin-1", errors="replace")


def parse_pdf(file_bytes: bytes) -> str:
    """
    Extract all text from a PDF byte stream using pypdf.

    Returns an empty string rather than raising if the PDF contains no
    extractable text (e.g. a scanned image PDF).
    """
    try:
        import io
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(file_bytes))
        pages: list[str] = []

        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(text)
            else:
                logger.debug("Page %d yielded no extractable text.", page_num)

        full_text = "\n\n".join(pages)
        logger.info("PDF parsed. pages=%d chars=%d", len(reader.pages), len(full_text))
        return full_text

    except Exception as exc:
        logger.error("PDF parsing failed: %s", exc, exc_info=True)
        return ""


def parse_file(file_bytes: bytes, extension: str) -> Optional[str]:
    """
    Dispatch to the correct parser based on file extension.

    Args:
        file_bytes: Raw bytes of the uploaded file.
        extension:  Lowercase extension without leading dot ('pdf' or 'txt').

    Returns:
        Extracted text, or None if the extension is unsupported.
    """
    extension = extension.lower().lstrip(".")

    if extension == "pdf":
        return parse_pdf(file_bytes)
    elif extension == "txt":
        return parse_txt(file_bytes)

    logger.warning("Unsupported extension for parsing: %s", extension)
    return None
