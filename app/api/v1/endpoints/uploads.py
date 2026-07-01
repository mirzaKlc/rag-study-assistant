"""
Upload endpoints for course materials and past exam files.

Both endpoints follow the same contract:
  - Accept multipart/form-data with a single 'file' field
  - Validate extension (PDF or TXT only)
  - Enforce the configured size limit
  - Persist to the appropriate uploads sub-directory
  - Return upload metadata as JSON
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.core.security import check_file_size, validate_upload_file
from app.models.schemas import UploadCategory, UploadedFileResponse
from app.services.upload_service import index_uploaded_file, save_uploaded_file
from app.services.vector_service import VectorService, get_vector_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/uploads", tags=["Uploads"])


@router.post(
    "/course-content",
    response_model=UploadedFileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload course material (PDF or TXT)",
    description=(
        "Upload a PDF or TXT file containing lecture notes, textbook chapters, "
        "or any other study material. The file is stored and queued for indexing "
        "into the RAG vector store."
    ),
)
async def upload_course_content(
    file: Annotated[UploadFile, File(description="PDF or TXT course material")],
    vector_service: VectorService = Depends(get_vector_service),
) -> UploadedFileResponse:
    """
    Accept a course material upload, persist it, and index it for retrieval.

    Steps:
      1. Validate the file extension.
      2. Read and enforce the size limit.
      3. Delegate persistence to the upload service.
      4. Extract, chunk, and index the file so it's immediately searchable.
    """
    logger.info("Course content upload requested. filename=%s", file.filename)

    extension = validate_upload_file(file)
    file_bytes = await check_file_size(file)

    response = await save_uploaded_file(
        file_bytes=file_bytes,
        original_filename=file.filename or "unknown",
        extension=extension,
        category=UploadCategory.COURSE_CONTENT,
    )
    response.status = await index_uploaded_file(response, vector_service)

    logger.info(
        "Course content upload complete. file_id=%s status=%s",
        response.file_id, response.status,
    )
    return response


@router.post(
    "/past-exams",
    response_model=UploadedFileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a past exam file (PDF or TXT)",
    description=(
        "Upload a PDF or TXT file containing past exam questions. "
        "These are stored separately from course material and are used "
        "to fine-tune the question generation style."
    ),
)
async def upload_past_exam(
    file: Annotated[UploadFile, File(description="PDF or TXT past exam file")],
    vector_service: VectorService = Depends(get_vector_service),
) -> UploadedFileResponse:
    """
    Accept a past-exam upload, persist it, and index it for retrieval.

    Steps:
      1. Validate the file extension.
      2. Read and enforce the size limit.
      3. Delegate persistence to the upload service.
      4. Extract, chunk, and index the file so it's immediately searchable.
    """
    logger.info("Past exam upload requested. filename=%s", file.filename)

    extension = validate_upload_file(file)
    file_bytes = await check_file_size(file)

    response = await save_uploaded_file(
        file_bytes=file_bytes,
        original_filename=file.filename or "unknown",
        extension=extension,
        category=UploadCategory.PAST_EXAM,
    )
    response.status = await index_uploaded_file(response, vector_service)

    logger.info(
        "Past exam upload complete. file_id=%s status=%s",
        response.file_id, response.status,
    )
    return response
