"""
Upload service — business logic for persisting uploaded files.

Separates I/O concerns from the API layer. The endpoint hands raw bytes
and metadata here; this service decides how to store them.
"""

import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings
from app.models.schemas import DocumentStatus, UploadCategory, UploadedFileResponse
from app.services.vector_service import VectorService
from app.utils.file_processors import process_document

logger = logging.getLogger(__name__)
settings = get_settings()


def _resolve_upload_dir(category: UploadCategory) -> Path:
    """Return the correct upload directory for the given category."""
    if category == UploadCategory.COURSE_CONTENT:
        return settings.content_upload_dir
    return settings.exams_upload_dir


def _build_stored_filename(original_filename: str) -> str:
    """
    Prefix the original filename with a UUID4 to guarantee uniqueness.

    Format: <uuid>_<original_filename>
    Using UUID rather than a timestamp avoids collisions under concurrent
    uploads and keeps filenames sortable by creation identity.
    """
    unique_prefix = uuid.uuid4().hex
    safe_name = Path(original_filename).name  # strip any path traversal attempts
    return f"{unique_prefix}_{safe_name}"


async def save_uploaded_file(
    file_bytes: bytes,
    original_filename: str,
    extension: str,
    category: UploadCategory,
) -> UploadedFileResponse:
    """
    Persist the file bytes to the appropriate uploads sub-directory.

    Args:
        file_bytes:        Raw bytes of the uploaded file.
        original_filename: Filename as provided by the client.
        extension:         Validated lowercase extension ('pdf' or 'txt').
        category:          Determines the storage sub-directory.

    Returns:
        UploadedFileResponse with metadata about the stored file.

    Raises:
        IOError: If the file cannot be written to disk.
    """
    upload_dir = _resolve_upload_dir(category)
    upload_dir.mkdir(parents=True, exist_ok=True)

    stored_filename = _build_stored_filename(original_filename)
    destination = upload_dir / stored_filename

    try:
        destination.write_bytes(file_bytes)
        logger.info(
            "File saved. category=%s stored_filename=%s size_bytes=%d",
            category.value,
            stored_filename,
            len(file_bytes),
        )
    except OSError as exc:
        logger.error("Failed to write file %s: %s", destination, exc, exc_info=True)
        raise

    return UploadedFileResponse(
        file_id=stored_filename.split("_")[0],  # the UUID prefix
        original_filename=original_filename,
        stored_filename=stored_filename,
        category=category,
        size_bytes=len(file_bytes),
        extension=extension,
        uploaded_at=datetime.now(timezone.utc),
        status=DocumentStatus.PENDING,
    )


async def index_uploaded_file(
    response: UploadedFileResponse,
    vector_service: VectorService,
) -> DocumentStatus:
    """
    Extract, chunk, and index a freshly saved upload into the vector store.

    Runs synchronously as part of the upload request so that by the time the
    client receives a response, the file is already searchable (or the
    response says it isn't). The saved file itself is never removed on
    failure — only its searchability is affected.

    Args:
        response:       The UploadedFileResponse just returned by save_uploaded_file.
        vector_service: Service used to embed and index the extracted chunks.

    Returns:
        DocumentStatus.INDEXED on success, DocumentStatus.FAILED otherwise.
    """
    file_path = _resolve_upload_dir(response.category) / response.stored_filename

    try:
        chunks = await process_document(file_path, source_filename=response.stored_filename)
        if not chunks:
            logger.warning(
                "No extractable text; indexing skipped. file_id=%s", response.file_id
            )
            return DocumentStatus.FAILED

        indexed_count = await vector_service.index_chunks(chunks, response.category)
        if indexed_count == 0:
            return DocumentStatus.FAILED

        logger.info("File indexed. file_id=%s chunks=%d", response.file_id, indexed_count)
        return DocumentStatus.INDEXED

    except Exception as exc:
        logger.error(
            "Indexing failed. file_id=%s error=%s", response.file_id, exc, exc_info=True
        )
        return DocumentStatus.FAILED
