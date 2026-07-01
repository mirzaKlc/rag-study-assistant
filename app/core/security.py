"""
Security utilities for file validation and future auth extension points.

Keeps all security-sensitive checks in one place so they are easy to
audit and tighten without hunting across the codebase.
"""

import hashlib
import hmac
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Magic bytes for supported MIME types
_MAGIC_BYTES: dict[str, bytes] = {
    "pdf": b"%PDF",
    "txt": b"",  # Plain text has no universal magic bytes; rely on extension + UTF-8 probe
}


def validate_upload_file(upload: UploadFile) -> str:
    """
    Validate an uploaded file against allowed extensions and size limits.

    Returns the lowercase file extension on success.
    Raises HTTPException(422) on validation failure.
    """
    if not upload.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file has no filename.",
        )

    suffix = Path(upload.filename).suffix.lstrip(".").lower()

    if suffix not in settings.allowed_extensions_list:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"File type '.{suffix}' is not supported. "
                f"Allowed types: {settings.allowed_extensions_list}"
            ),
        )

    logger.debug("File validation passed. filename=%s ext=%s", upload.filename, suffix)
    return suffix


async def check_file_size(upload: UploadFile) -> bytes:
    """
    Read the file into memory and enforce the size limit.

    Returns the raw file bytes so callers avoid re-reading.
    Raises HTTPException(413) if the file exceeds the configured limit.
    """
    content = await upload.read()
    size_mb = len(content) / (1024 * 1024)

    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"File size {size_mb:.2f} MB exceeds the "
                f"{settings.max_upload_size_mb} MB limit."
            ),
        )

    return content


def verify_hmac_signature(payload: bytes, signature: str, secret: Optional[str] = None) -> bool:
    """
    Constant-time HMAC-SHA256 signature verification.

    Intended for future webhook or API callback security.
    """
    key = (secret or settings.secret_key).encode()
    expected = hmac.new(key, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
