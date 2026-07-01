"""
AI endpoints — Gemini-backed summarization and exam-style question generation.

Both endpoints depend on ``AIService`` and translate its domain exceptions
into HTTP responses:
  - ContentNotIndexedError -> 404 (the referenced file has not been indexed)
  - AIGenerationError      -> 502 (the upstream Gemini call failed)
Any other exception falls through to the global catch-all handler in main.py.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.schemas import (
    GenerateQuestionsRequest,
    GenerateQuestionsResponse,
    SummarizeRequest,
    SummarizeResponse,
)
from app.services.ai_service import (
    AIGenerationError,
    AIService,
    ContentNotIndexedError,
    get_ai_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI"])


@router.post(
    "/summarize",
    response_model=SummarizeResponse,
    summary="Generate an academic summary of indexed course content",
    description=(
        "Generate a markdown-formatted academic summary from a previously "
        "uploaded and indexed course-content file, optionally focused on a topic."
    ),
)
async def summarize(
    payload: SummarizeRequest,
    ai_service: AIService = Depends(get_ai_service),
) -> SummarizeResponse:
    logger.info("Summarize requested. content_file_id=%s", payload.content_file_id)

    try:
        response = await ai_service.generate_summary(
            content_file_id=payload.content_file_id,
            topic_hint=payload.topic_hint,
        )
    except ContentNotIndexedError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AIGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    logger.info("Summarize complete. content_file_id=%s", payload.content_file_id)
    return response


@router.post(
    "/generate-questions",
    response_model=GenerateQuestionsResponse,
    summary="Generate exam-style practice questions",
    description=(
        "Generate exam-style practice questions from a course-content file, "
        "styled after a previously uploaded past-exam file."
    ),
)
async def generate_questions(
    payload: GenerateQuestionsRequest,
    ai_service: AIService = Depends(get_ai_service),
) -> GenerateQuestionsResponse:
    logger.info(
        "Question generation requested. content_file_id=%s exam_file_id=%s count=%d",
        payload.content_file_id, payload.exam_file_id, payload.count,
    )

    try:
        response = await ai_service.generate_questions(
            content_file_id=payload.content_file_id,
            exam_file_id=payload.exam_file_id,
            count=payload.count,
            topic_hint=payload.topic_hint,
        )
    except ContentNotIndexedError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AIGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    logger.info(
        "Question generation complete. content_file_id=%s returned=%d",
        payload.content_file_id, response.count,
    )
    return response
