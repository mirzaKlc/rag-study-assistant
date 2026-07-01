"""
Pydantic schemas for API request/response contracts.

All public-facing data shapes are defined here so the API layer
and service layer share a single source of truth.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class UploadCategory(str, Enum):
    """Discriminates between the two upload buckets."""
    COURSE_CONTENT = "course_content"
    PAST_EXAM = "past_exam"


class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Upload schemas
# ---------------------------------------------------------------------------

class UploadedFileResponse(BaseModel):
    """Returned after a successful file upload."""

    file_id: str = Field(description="Unique identifier assigned to the stored file")
    original_filename: str = Field(description="The filename as provided by the client")
    stored_filename: str = Field(description="Filename on disk (UUID-prefixed for uniqueness)")
    category: UploadCategory
    size_bytes: int = Field(ge=0, description="File size in bytes")
    extension: str = Field(description="Lowercase file extension without the leading dot")
    uploaded_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the upload",
    )
    status: DocumentStatus = Field(default=DocumentStatus.PENDING)

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Error schemas
# ---------------------------------------------------------------------------

class ErrorDetail(BaseModel):
    """Standardised error envelope returned by the global exception handler."""

    status_code: int
    detail: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    path: Optional[str] = None
    request_id: Optional[str] = None

    model_config = {"json_schema_extra": {
        "example": {
            "status_code": 422,
            "detail": "File type '.docx' is not supported.",
            "timestamp": "2024-01-01T12:00:00Z",
            "path": "/api/v1/uploads/course-content",
        }
    }}


# ---------------------------------------------------------------------------
# AI — Summary schemas
# ---------------------------------------------------------------------------

class SummarizeRequest(BaseModel):
    """Request body for the /ai/summarize endpoint."""

    content_file_id: str = Field(
        description="The file_id returned when the course material was uploaded.",
        min_length=1,
    )
    topic_hint: Optional[str] = Field(
        default=None,
        description=(
            "Optional keyword or phrase to focus the summary on a specific topic. "
            "When omitted, the entire indexed content is summarised."
        ),
        max_length=300,
    )

    model_config = {"json_schema_extra": {
        "example": {
            "content_file_id": "a3f1bc2d...",
            "topic_hint": "Veri yapıları ve algoritmalar",
        }
    }}


class SummarizeResponse(BaseModel):
    """Returned by /ai/summarize."""

    content_file_id: str
    summary: str = Field(description="Markdown-formatted academic summary")
    model_used: str
    context_chunks_used: int = Field(ge=0)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# AI — Question generation schemas
# ---------------------------------------------------------------------------

class QuestionItem(BaseModel):
    """A single generated exam question with full solution."""

    question_number: int = Field(ge=1)
    question: str
    options: Optional[list[str]] = Field(
        default=None,
        description="Answer options for multiple-choice questions; null for open-ended.",
    )
    correct_answer: str
    detailed_solution: str
    difficulty: Optional[str] = Field(
        default=None,
        description="'easy' | 'medium' | 'hard'",
    )
    question_type: Optional[str] = Field(
        default=None,
        description="'multiple_choice' | 'open_ended' | 'coding' | 'true_false'",
    )


class GenerateQuestionsRequest(BaseModel):
    """Request body for /ai/generate-questions."""

    content_file_id: str = Field(
        description="file_id of the course material to base questions on.",
        min_length=1,
    )
    exam_file_id: str = Field(
        description="file_id of the past exam to derive question style from.",
        min_length=1,
    )
    count: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of questions to generate (1–20).",
    )
    topic_hint: Optional[str] = Field(
        default=None,
        description="Optional topic focus for the generated questions.",
        max_length=300,
    )

    model_config = {"json_schema_extra": {
        "example": {
            "content_file_id": "a3f1bc2d...",
            "exam_file_id": "9e4d77fa...",
            "count": 5,
            "topic_hint": "Bağlantılı listeler",
        }
    }}


class GenerateQuestionsResponse(BaseModel):
    """Returned by /ai/generate-questions."""

    content_file_id: str
    exam_file_id: str
    questions: list[QuestionItem]
    count: int = Field(description="Actual number of questions returned")
    model_used: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Health check schema
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    environment: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
