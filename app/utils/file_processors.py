"""
Document processing pipeline: text extraction and recursive chunking.

Design goals
------------
* Extraction is page-aware for PDFs so metadata survives into the vector store.
* The chunker replicates LangChain's RecursiveCharacterTextSplitter algorithm
  without the LangChain dependency, keeping the stack lean.
* All I/O is wrapped in asyncio.to_thread so the event loop is never blocked.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Ordered list of separators tried by the recursive splitter.
# Wider separators are preferred; "" means character-level as last resort.
_SEPARATORS: list[str] = ["\n\n", "\n", ". ", "! ", "? ", "; ", " ", ""]


# ---------------------------------------------------------------------------
# Data contract
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TextChunk:
    """One indexable piece of a document, carrying provenance metadata."""

    text: str
    source_file: str        # stored filename on disk (UUID-prefixed)
    page_number: int        # 1-based for PDF; 0 for TXT (no pages)
    chunk_index: int        # 0-based index within the page's chunk list
    total_chunks: int       # total chunks produced from this document
    char_count: int = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "char_count", len(self.text))

    @property
    def chunk_id(self) -> str:
        """Deterministic, human-readable unique ID for use as ChromaDB document ID."""
        safe_name = Path(self.source_file).stem[:40]
        return f"{safe_name}_p{self.page_number}_c{self.chunk_index}"


# ---------------------------------------------------------------------------
# Recursive text splitter
# ---------------------------------------------------------------------------

class RecursiveTextSplitter:
    """
    Split long text into overlapping chunks using a hierarchy of separators.

    Algorithm (mirrors LangChain's RecursiveCharacterTextSplitter):
      1. Try separators in order; use the first one found in the text.
      2. Splits smaller than chunk_size are merged into chunks with overlap.
      3. Splits larger than chunk_size are recursively split with the next separator.

    Args:
        chunk_size:    Maximum number of characters per chunk.
        chunk_overlap: Characters carried over from the end of the previous chunk.
    """

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> None:
        self._chunk_size = chunk_size or settings.chunk_size
        self._chunk_overlap = chunk_overlap or settings.chunk_overlap

        if self._chunk_overlap >= self._chunk_size:
            raise ValueError(
                f"chunk_overlap ({self._chunk_overlap}) must be "
                f"less than chunk_size ({self._chunk_size})."
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def split_text(self, text: str) -> list[str]:
        """Return a list of non-empty text chunks."""
        raw = self._split_recursive(text.strip(), _SEPARATORS)
        return [c for c in raw if c.strip()]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _split_recursive(self, text: str, separators: list[str]) -> list[str]:
        """
        Recursively split `text` using the first matching separator.
        Pieces that are still too large fall through to the next separator.
        """
        if not text:
            return []

        # Pick the first separator that actually appears in the text
        chosen_sep = separators[-1]  # fallback: character-level ("")
        remaining_seps: list[str] = []
        for i, sep in enumerate(separators):
            if sep == "" or sep in text:
                chosen_sep = sep
                remaining_seps = separators[i + 1 :]
                break

        splits = text.split(chosen_sep) if chosen_sep else list(text)

        # Classify splits: small (ready to merge) vs. large (need further splitting)
        final_chunks: list[str] = []
        pending_small: list[str] = []

        for piece in splits:
            if len(piece) <= self._chunk_size:
                pending_small.append(piece)
            else:
                # Flush small pieces first
                if pending_small:
                    final_chunks.extend(
                        self._merge_splits(pending_small, chosen_sep)
                    )
                    pending_small = []

                if remaining_seps:
                    # Recurse with a narrower separator
                    final_chunks.extend(
                        self._split_recursive(piece, remaining_seps)
                    )
                else:
                    # No separator left — force the oversized piece as-is
                    final_chunks.append(piece)

        if pending_small:
            final_chunks.extend(self._merge_splits(pending_small, chosen_sep))

        return final_chunks

    def _merge_splits(self, splits: list[str], separator: str) -> list[str]:
        """
        Merge small splits into chunks of at most `chunk_size` characters,
        carrying `chunk_overlap` characters from the end of each chunk into
        the start of the next.
        """
        chunks: list[str] = []
        current: list[str] = []
        current_len = 0
        sep_len = len(separator)

        for piece in splits:
            piece_len = len(piece)
            # Length if we append this piece to current (with separator if not first)
            added_len = (sep_len if current else 0) + piece_len

            if current_len + added_len > self._chunk_size and current:
                # Emit the current chunk
                chunks.append(separator.join(current))

                # Trim from the front to maintain the overlap budget
                while current and current_len > self._chunk_overlap:
                    dropped = current.pop(0)
                    current_len -= len(dropped) + (sep_len if current else 0)

            current.append(piece)
            current_len += (sep_len if len(current) > 1 else 0) + piece_len

        if current:
            chunks.append(separator.join(current))

        return chunks


# ---------------------------------------------------------------------------
# Text extraction — PDF
# ---------------------------------------------------------------------------

def _extract_pdf_sync(file_path: Path) -> list[tuple[int, str]]:
    """
    Synchronous PDF extraction (runs in a thread pool via the async wrapper).

    Uses pdfplumber as primary extractor.  Falls back to pypdf on any
    per-page error so a single bad page does not abort the whole document.

    Returns:
        List of (1-based page number, extracted text) tuples.
        Pages that yield no text are silently skipped.
    """
    pages: list[tuple[int, str]] = []

    # ── Primary: pdfplumber ─────────────────────────────────────────────
    try:
        import pdfplumber

        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                try:
                    text: Optional[str] = page.extract_text()
                    if text and text.strip():
                        pages.append((page_num, text))
                    else:
                        logger.debug(
                            "pdfplumber: page %d has no extractable text. file=%s",
                            page_num, file_path.name,
                        )
                except Exception as page_err:
                    logger.warning(
                        "pdfplumber: error on page %d of %s — %s",
                        page_num, file_path.name, page_err,
                    )

        logger.info(
            "PDF extracted via pdfplumber. file=%s pages_with_text=%d",
            file_path.name, len(pages),
        )
        return pages

    except Exception as plumber_err:
        logger.warning(
            "pdfplumber failed for %s (%s). Falling back to pypdf.",
            file_path.name, plumber_err,
        )

    # ── Fallback: pypdf ─────────────────────────────────────────────────
    try:
        import io
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(file_path.read_bytes()))
        for page_num, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
                if text.strip():
                    pages.append((page_num, text))
            except Exception as page_err:
                logger.warning(
                    "pypdf: error on page %d of %s — %s",
                    page_num, file_path.name, page_err,
                )

        logger.info(
            "PDF extracted via pypdf fallback. file=%s pages_with_text=%d",
            file_path.name, len(pages),
        )
        return pages

    except Exception as pypdf_err:
        logger.error(
            "Both PDF extractors failed for %s: %s",
            file_path.name, pypdf_err, exc_info=True,
        )
        return []


async def extract_pages_from_pdf(file_path: Path) -> list[tuple[int, str]]:
    """Async wrapper — delegates blocking I/O to a thread pool."""
    return await asyncio.to_thread(_extract_pdf_sync, file_path)


# ---------------------------------------------------------------------------
# Text extraction — TXT
# ---------------------------------------------------------------------------

def _extract_txt_sync(file_path: Path) -> str:
    """Read a text file, trying UTF-8 first and latin-1 as fallback."""
    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        logger.warning(
            "UTF-8 decode failed for %s; retrying with latin-1.", file_path.name
        )
        return file_path.read_text(encoding="latin-1", errors="replace")


async def extract_from_txt(file_path: Path) -> str:
    """Async wrapper for plain-text extraction."""
    return await asyncio.to_thread(_extract_txt_sync, file_path)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

async def process_document(
    file_path: Path,
    source_filename: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[TextChunk]:
    """
    Full pipeline: extract text from `file_path`, chunk it, and return
    ``TextChunk`` objects annotated with provenance metadata.

    Args:
        file_path:       Absolute path to the stored file on disk.
        source_filename: Original filename as uploaded (for metadata only).
        chunk_size:      Override the default chunk size from config.
        chunk_overlap:   Override the default chunk overlap from config.

    Returns:
        Flat list of ``TextChunk`` objects ready for embedding and indexing.
    """
    extension = file_path.suffix.lstrip(".").lower()
    splitter = RecursiveTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    # --- Extract: returns list of (page_number, text) pairs ---------------
    page_texts: list[tuple[int, str]]

    if extension == "pdf":
        page_texts = await extract_pages_from_pdf(file_path)
    elif extension == "txt":
        full_text = await extract_from_txt(file_path)
        page_texts = [(0, full_text)] if full_text.strip() else []
    else:
        logger.error("Unsupported extension for processing: %s", extension)
        return []

    if not page_texts:
        logger.warning("No text extracted from %s.", file_path.name)
        return []

    # --- Chunk: each page's text is split independently -------------------
    all_raw_chunks: list[tuple[int, str]] = []  # (page_number, chunk_text)

    for page_num, page_text in page_texts:
        page_chunks = splitter.split_text(page_text)
        for chunk_text in page_chunks:
            all_raw_chunks.append((page_num, chunk_text))

    total = len(all_raw_chunks)

    chunks: list[TextChunk] = [
        TextChunk(
            text=chunk_text,
            source_file=source_filename,
            page_number=page_num,
            chunk_index=idx,
            total_chunks=total,
        )
        for idx, (page_num, chunk_text) in enumerate(all_raw_chunks)
    ]

    logger.info(
        "Document processed. file=%s pages=%d chunks=%d",
        source_filename, len(page_texts), total,
    )
    return chunks
