"""
AI service — Google Gemini integration for summarization and question generation.

Architecture
------------
AIService — owns the Gemini ``GenerativeModel`` and turns indexed document
chunks (retrieved via ``VectorService``) into:
  - generate_summary()    — academic, markdown-formatted summaries
  - generate_questions()  — exam-style practice questions with solutions

Retrieval strategy: whole-file context. ``VectorService.get_chunks_by_file_id``
returns every chunk for a given file_id; chunks are sorted by document order
and concatenated up to ``max_context_chars``. This keeps generation
deterministic and requires no changes to VectorService's semantic search API.

All blocking Gemini SDK calls are dispatched to a thread pool so the async
event loop stays free, mirroring the pattern used in vector_service.py.
"""

from __future__ import annotations

import asyncio
import json
import logging
from functools import lru_cache

import google.generativeai as genai

from app.core.config import Settings, get_settings
from app.models.schemas import (
    GenerateQuestionsResponse,
    QuestionItem,
    SummarizeResponse,
    UploadCategory,
)
from app.services.vector_service import VectorService, get_vector_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ContentNotIndexedError(ValueError):
    """Raised when a requested file_id has no indexed chunks."""


class AIGenerationError(RuntimeError):
    """Raised when the Gemini API call fails or returns an unusable response."""


# ---------------------------------------------------------------------------
# Context assembly
# ---------------------------------------------------------------------------

async def _load_file_context(
    vector_service: VectorService,
    file_id: str,
    category: UploadCategory,
    max_chars: int,
) -> tuple[str, int]:
    """
    Fetch every indexed chunk for ``file_id``, sort by document order, and
    concatenate up to ``max_chars``.

    Args:
        vector_service: Service used to read indexed chunks.
        file_id:        UUID hex prefix of the stored filename.
        category:       Which collection to read from.
        max_chars:      Character budget for the returned context.

    Returns:
        Tuple of (context_text, chunk_count_used).

    Raises:
        ContentNotIndexedError: If the file has no indexed chunks.
    """
    chunks = await vector_service.get_chunks_by_file_id(file_id, category)
    if not chunks:
        raise ContentNotIndexedError(
            f"No indexed content found for file_id='{file_id}' in category='{category.value}'. "
            "Has the file finished processing?"
        )

    chunks.sort(key=lambda c: (c["page_number"], c["chunk_index"]))

    pieces: list[str] = []
    total_len = 0
    used = 0

    for chunk in chunks:
        text = chunk["text"]
        if total_len + len(text) > max_chars:
            if used == 0:
                # A single oversized chunk — include a truncated slice so
                # context is never empty.
                pieces.append(text[:max_chars])
                used = 1
            break
        pieces.append(text)
        total_len += len(text)
        used += 1

    return "\n\n".join(pieces), used


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _build_summary_prompt(context: str, topic_hint: str | None) -> str:
    focus = (
        f"\n\nÖzellikle şu konuya odaklan: {topic_hint}"
        if topic_hint
        else ""
    )
    return (
        "Aşağıda bir ders materyalinden alınmış içerik bulunmaktadır. "
        "Bu içeriği bir öğrencinin sınava çalışırken kullanabileceği, "
        "akademik ve anlaşılır bir özet haline getir. "
        "Çıktıyı Markdown formatında, başlıklar ve madde işaretleri kullanarak yapılandır."
        f"{focus}\n\n"
        "--- DERS İÇERİĞİ ---\n"
        f"{context}\n"
        "--- DERS İÇERİĞİ SONU ---\n"
    )


def _build_questions_prompt(
    content_context: str,
    exam_context: str,
    count: int,
    topic_hint: str | None,
) -> str:
    focus = (
        f"\n\nSorular özellikle şu konuya odaklanmalı: {topic_hint}"
        if topic_hint
        else ""
    )
    return (
        "Aşağıda bir ders materyali ve o derse ait geçmiş bir sınavdan örnek "
        "sorular bulunmaktadır. Ders materyaline dayanarak, geçmiş sınavın "
        "soru tarzına ve zorluk seviyesine benzer, tam olarak "
        f"{count} adet yeni pratik sınav sorusu üret.{focus}\n\n"
        "--- DERS İÇERİĞİ ---\n"
        f"{content_context}\n"
        "--- DERS İÇERİĞİ SONU ---\n\n"
        "--- GEÇMİŞ SINAV ÖRNEĞİ (sadece stil referansı) ---\n"
        f"{exam_context}\n"
        "--- GEÇMİŞ SINAV ÖRNEĞİ SONU ---\n\n"
        "Yanıtını SADECE şu formatta bir JSON dizisi olarak ver, başka hiçbir "
        "metin ekleme:\n"
        "[\n"
        "  {\n"
        '    "question": "Soru metni",\n'
        '    "options": ["A) ...", "B) ...", "C) ...", "D) ..."] veya null,\n'
        '    "correct_answer": "Doğru cevap",\n'
        '    "detailed_solution": "Adım adım detaylı çözüm açıklaması",\n'
        '    "difficulty": "easy" | "medium" | "hard",\n'
        '    "question_type": "multiple_choice" | "open_ended" | "coding" | "true_false"\n'
        "  }\n"
        "]\n"
        f"Dizi tam olarak {count} eleman içermelidir."
    )


# ---------------------------------------------------------------------------
# Question parsing
# ---------------------------------------------------------------------------

def _parse_questions(raw_json: str, expected_count: int) -> list[QuestionItem]:
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise AIGenerationError("Gemini yanıtı geçerli JSON değil.") from exc

    items = data.get("questions", []) if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise AIGenerationError("Beklenmeyen yanıt formatı: soru listesi bulunamadı.")

    questions: list[QuestionItem] = []
    for idx, item in enumerate(items[:expected_count], start=1):
        if not isinstance(item, dict):
            logger.warning("Skipping malformed question item %d: not an object.", idx)
            continue
        item.setdefault("question_number", idx)
        try:
            questions.append(QuestionItem.model_validate(item))
        except Exception as exc:
            logger.warning("Skipping malformed question item %d: %s", idx, exc)

    if not questions:
        raise AIGenerationError("Gemini hiçbir geçerli soru üretmedi.")

    return questions


# ---------------------------------------------------------------------------
# AI service
# ---------------------------------------------------------------------------

class AIService:
    """
    Gemini-backed generation layer for summaries and exam-style questions.

    Args:
        vector_service: Used to read previously indexed document chunks.
        settings:       Application settings (Gemini model, temperatures, budgets).
    """

    def __init__(self, vector_service: VectorService, settings: Settings) -> None:
        self._vector_service = vector_service
        self._settings = settings

        genai.configure(api_key=settings.gemini_api_key)
        self._model = genai.GenerativeModel(settings.gemini_model)
        logger.info("AIService initialised. model=%s", settings.gemini_model)

    # ------------------------------------------------------------------
    # Gemini call wrapper
    # ------------------------------------------------------------------

    async def _generate(self, prompt: str, *, temperature: float, json_mode: bool) -> str:
        """
        Run a single Gemini generation call in a thread pool.

        Raises:
            AIGenerationError: On SDK errors, safety blocks, or empty responses.
        """
        generation_config = genai.GenerationConfig(
            temperature=temperature,
            response_mime_type="application/json" if json_mode else "text/plain",
        )

        def _call() -> str:
            response = self._model.generate_content(
                prompt, generation_config=generation_config
            )
            if not response.candidates:
                block_reason = getattr(response.prompt_feedback, "block_reason", None)
                raise AIGenerationError(
                    f"Gemini yanıtı engellendi veya boş döndü. block_reason={block_reason}"
                )
            return response.text

        try:
            return await asyncio.to_thread(_call)
        except AIGenerationError:
            raise
        except Exception as exc:
            logger.error("Gemini generation failed. error=%s", exc, exc_info=True)
            raise AIGenerationError("Gemini API isteği başarısız oldu.") from exc

    # ------------------------------------------------------------------
    # Summarization
    # ------------------------------------------------------------------

    async def generate_summary(
        self,
        content_file_id: str,
        topic_hint: str | None = None,
    ) -> SummarizeResponse:
        """
        Generate a markdown academic summary of an indexed course-content file.

        Raises:
            ContentNotIndexedError: If the file has no indexed chunks.
            AIGenerationError: If the Gemini call fails.
        """
        context, chunks_used = await _load_file_context(
            self._vector_service,
            content_file_id,
            UploadCategory.COURSE_CONTENT,
            self._settings.max_context_chars,
        )

        prompt = _build_summary_prompt(context, topic_hint)
        text = await self._generate(
            prompt, temperature=self._settings.gemini_summary_temperature, json_mode=False
        )

        logger.info(
            "Summary generated. content_file_id=%s chunks_used=%d", content_file_id, chunks_used
        )
        return SummarizeResponse(
            content_file_id=content_file_id,
            summary=text.strip(),
            model_used=self._settings.gemini_model,
            context_chunks_used=chunks_used,
        )

    # ------------------------------------------------------------------
    # Question generation
    # ------------------------------------------------------------------

    async def generate_questions(
        self,
        content_file_id: str,
        exam_file_id: str,
        count: int = 5,
        topic_hint: str | None = None,
    ) -> GenerateQuestionsResponse:
        """
        Generate exam-style practice questions from course content, styled
        after a past exam.

        Raises:
            ContentNotIndexedError: If either file has no indexed chunks.
            AIGenerationError: If the Gemini call or response parsing fails.
        """
        content_budget = int(self._settings.max_context_chars * 0.7)
        exam_budget = self._settings.max_context_chars - content_budget

        content_context, _ = await _load_file_context(
            self._vector_service, content_file_id, UploadCategory.COURSE_CONTENT, content_budget
        )
        exam_context, _ = await _load_file_context(
            self._vector_service, exam_file_id, UploadCategory.PAST_EXAM, exam_budget
        )

        prompt = _build_questions_prompt(content_context, exam_context, count, topic_hint)
        raw = await self._generate(
            prompt, temperature=self._settings.gemini_question_temperature, json_mode=True
        )

        questions = _parse_questions(raw, count)

        logger.info(
            "Questions generated. content_file_id=%s exam_file_id=%s requested=%d returned=%d",
            content_file_id, exam_file_id, count, len(questions),
        )
        return GenerateQuestionsResponse(
            content_file_id=content_file_id,
            exam_file_id=exam_file_id,
            questions=questions,
            count=len(questions),
            model_used=self._settings.gemini_model,
        )


# ---------------------------------------------------------------------------
# Singleton factory (FastAPI dependency)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_ai_service() -> AIService:
    """
    Return the application-wide ``AIService`` singleton.

    Use this as a FastAPI dependency::

        from app.services.ai_service import get_ai_service
        from fastapi import Depends

        async def my_endpoint(ai: AIService = Depends(get_ai_service)):
            ...
    """
    settings = get_settings()
    vector_service = get_vector_service()
    service = AIService(vector_service=vector_service, settings=settings)
    return service
