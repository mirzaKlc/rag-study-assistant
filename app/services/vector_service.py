"""
Vector database service — embedding abstraction + ChromaDB integration.

Architecture
------------
EmbeddingProvider (ABC)
  ├── SentenceTransformerProvider   — local, no API key needed
  └── GeminiEmbeddingProvider       — Google Gemini Embedding API

VectorService                        — ChromaDB CRUD, uses any EmbeddingProvider
  ├── index_chunks()                 — embed + upsert into the correct collection
  └── similarity_search()           — query the correct collection

Switching the embedding backend requires only changing EMBEDDING_PROVIDER in .env.
All blocking calls are dispatched to a thread pool so the async event loop stays free.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import chromadb
from chromadb import Collection, PersistentClient

from app.core.config import Settings, get_settings
from app.models.schemas import UploadCategory
from app.utils.file_processors import TextChunk

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SearchResult:
    """One item returned by a similarity search."""

    text: str
    source_file: str
    page_number: int
    chunk_index: int
    distance: float  # lower = more similar (cosine distance in [0, 2])

    @property
    def similarity_score(self) -> float:
        """Convert cosine distance to a [0, 1] similarity score."""
        return max(0.0, 1.0 - self.distance / 2.0)


# ---------------------------------------------------------------------------
# Embedding providers
# ---------------------------------------------------------------------------

class EmbeddingProvider(ABC):
    """
    Abstract base for all embedding backends.

    Subclasses implement the synchronous ``embed_texts`` method.
    The async wrapper ``aembed_texts`` is provided here and dispatches
    to a thread pool — subclasses do not need to override it.
    """

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Embed a batch of texts.

        Args:
            texts: Non-empty list of strings to embed.

        Returns:
            List of float vectors, one per input text.
        """
        ...

    async def aembed_texts(self, texts: list[str]) -> list[list[float]]:
        """Async wrapper — runs ``embed_texts`` in the default thread pool."""
        return await asyncio.to_thread(self.embed_texts, texts)

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Embedding vector size. Used for collection metadata."""
        ...


class SentenceTransformerProvider(EmbeddingProvider):
    """
    Local embedding using sentence-transformers.

    The model is downloaded once on first use and cached in memory.
    No API key or network access required after the initial download.

    Args:
        model_name: HuggingFace model ID, e.g. "all-MiniLM-L6-v2".
    """

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model: Any = None  # lazy load

    def _load_model(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading SentenceTransformer model: %s", self._model_name)
            self._model = SentenceTransformer(self._model_name)
            logger.info(
                "Model loaded. embedding_dim=%d", self._model.get_sentence_embedding_dimension()
            )
        return self._model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        model = self._load_model()
        embeddings = model.encode(texts, batch_size=64, show_progress_bar=False)
        return embeddings.tolist()

    @property
    def dimension(self) -> int:
        return self._load_model().get_sentence_embedding_dimension()


class GeminiEmbeddingProvider(EmbeddingProvider):
    """
    Embedding via Google Gemini Embedding API (text-embedding-004).

    Texts are sent in batches of ``_BATCH_SIZE`` to stay within API limits.
    Requires ``GEMINI_API_KEY`` to be set.

    Args:
        api_key:    Google Gemini API key.
        model_name: Gemini embedding model ID.
    """

    _BATCH_SIZE = 100
    _VECTOR_DIM = 768  # text-embedding-004 output dimension

    def __init__(self, api_key: str, model_name: str = "models/text-embedding-004") -> None:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        self._genai = genai
        self._model_name = model_name
        logger.info("GeminiEmbeddingProvider initialised. model=%s", model_name)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float]] = []

        for i in range(0, len(texts), self._BATCH_SIZE):
            batch = texts[i : i + self._BATCH_SIZE]
            for text in batch:
                response = self._genai.embed_content(
                    model=self._model_name,
                    content=text,
                    task_type="retrieval_document",
                )
                results.append(response["embedding"])

        return results

    @property
    def dimension(self) -> int:
        return self._VECTOR_DIM


# ---------------------------------------------------------------------------
# Embedding provider factory
# ---------------------------------------------------------------------------

def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    """
    Instantiate the configured embedding provider.

    Reads ``EMBEDDING_PROVIDER`` and ``EMBEDDING_MODEL`` from settings.
    Raises ``ValueError`` for unknown provider names.
    """
    provider_name = settings.embedding_provider.lower()

    if provider_name == "sentence_transformer":
        return SentenceTransformerProvider(model_name=settings.embedding_model)

    if provider_name == "gemini":
        return GeminiEmbeddingProvider(
            api_key=settings.gemini_api_key,
            model_name=f"models/{settings.embedding_model}",
        )

    raise ValueError(
        f"Unknown embedding provider: '{provider_name}'. "
        "Choose 'sentence_transformer' or 'gemini'."
    )


# ---------------------------------------------------------------------------
# ChromaDB collection names
# ---------------------------------------------------------------------------

_COURSE_CONTENT_COLLECTION = "course_content"
_PAST_EXAMS_COLLECTION = "past_exams"


def _collection_for_category(category: UploadCategory) -> str:
    return (
        _COURSE_CONTENT_COLLECTION
        if category == UploadCategory.COURSE_CONTENT
        else _PAST_EXAMS_COLLECTION
    )


# ---------------------------------------------------------------------------
# Vector service
# ---------------------------------------------------------------------------

class VectorService:
    """
    Manages document indexing and retrieval against a persistent ChromaDB store.

    Uses ``upsert`` (not ``add``) so re-uploading a document overwrites its
    previous vectors without raising duplicate-ID errors.

    Args:
        embedding_provider: Any ``EmbeddingProvider`` implementation.
        settings:           Application settings (for DB path).
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        settings: Settings,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._settings = settings
        self._client: PersistentClient | None = None

    # ------------------------------------------------------------------
    # ChromaDB client & collection access
    # ------------------------------------------------------------------

    def _get_client(self) -> PersistentClient:
        if self._client is None:
            db_path = self._settings.chroma_db_path
            logger.info("Connecting to ChromaDB. path=%s", db_path)
            self._client = chromadb.PersistentClient(path=db_path)
        return self._client

    def _get_collection(self, name: str) -> Collection:
        """Return (or create) a cosine-distance collection by name."""
        return self._get_client().get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    async def index_chunks(
        self,
        chunks: list[TextChunk],
        category: UploadCategory,
    ) -> int:
        """
        Embed and upsert a list of ``TextChunk`` objects into ChromaDB.

        Args:
            chunks:   Chunks produced by ``process_document()``.
            category: Determines which collection receives the data.

        Returns:
            Number of chunks successfully indexed.

        Raises:
            RuntimeError: If the ChromaDB upsert fails.
        """
        if not chunks:
            logger.warning("index_chunks called with an empty chunk list.")
            return 0

        collection_name = _collection_for_category(category)
        texts = [chunk.text for chunk in chunks]

        logger.info(
            "Embedding %d chunks for collection '%s'...", len(chunks), collection_name
        )
        embeddings = await self._embedding_provider.aembed_texts(texts)

        ids = [chunk.chunk_id for chunk in chunks]
        metadatas = [
            {
                # UUID prefix stored separately so we can filter by file_id directly
                "file_id": chunk.source_file.split("_")[0],
                "source_file": chunk.source_file,
                "page_number": chunk.page_number,
                "chunk_index": chunk.chunk_index,
                "total_chunks": chunk.total_chunks,
                "char_count": chunk.char_count,
            }
            for chunk in chunks
        ]

        def _upsert() -> None:
            collection = self._get_collection(collection_name)
            collection.upsert(
                ids=ids,
                documents=texts,
                embeddings=embeddings,
                metadatas=metadatas,
            )

        try:
            await asyncio.to_thread(_upsert)
        except Exception as exc:
            logger.error(
                "ChromaDB upsert failed. collection=%s error=%s",
                collection_name, exc, exc_info=True,
            )
            raise RuntimeError(f"Failed to index chunks into '{collection_name}'.") from exc

        logger.info(
            "Indexing complete. collection=%s chunks=%d source=%s",
            collection_name,
            len(chunks),
            chunks[0].source_file if chunks else "—",
        )
        return len(chunks)

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    async def similarity_search(
        self,
        query: str,
        category: UploadCategory,
        n_results: int = 5,
    ) -> list[SearchResult]:
        """
        Find the ``n_results`` most semantically similar chunks for ``query``.

        Args:
            query:     Natural-language question or search string.
            category:  Which collection to search.
            n_results: Maximum number of results to return.

        Returns:
            List of ``SearchResult`` objects sorted by ascending distance
            (most similar first).
        """
        collection_name = _collection_for_category(category)

        query_embedding = await self._embedding_provider.aembed_texts([query])

        def _query() -> dict:
            collection = self._get_collection(collection_name)
            return collection.query(
                query_embeddings=query_embedding,
                n_results=n_results,
                include=["documents", "metadatas", "distances"],
            )

        try:
            raw = await asyncio.to_thread(_query)
        except Exception as exc:
            logger.error(
                "ChromaDB query failed. collection=%s error=%s", collection_name, exc, exc_info=True
            )
            raise RuntimeError(f"Similarity search failed in '{collection_name}'.") from exc

        results: list[SearchResult] = []

        documents: list[str] = raw.get("documents", [[]])[0]
        metadatas: list[dict] = raw.get("metadatas", [[]])[0]
        distances: list[float] = raw.get("distances", [[]])[0]

        for doc, meta, dist in zip(documents, metadatas, distances):
            results.append(
                SearchResult(
                    text=doc,
                    source_file=meta.get("source_file", ""),
                    page_number=int(meta.get("page_number", 0)),
                    chunk_index=int(meta.get("chunk_index", 0)),
                    distance=dist,
                )
            )

        logger.info(
            "Similarity search returned %d results. collection=%s query_preview='%.60s'",
            len(results), collection_name, query,
        )
        return results

    # ------------------------------------------------------------------
    # File-scoped retrieval
    # ------------------------------------------------------------------

    async def get_chunks_by_file_id(
        self,
        file_id: str,
        category: UploadCategory,
    ) -> list[dict[str, Any]]:
        """
        Return every indexed chunk that belongs to the given ``file_id``.

        Unlike ``similarity_search``, this is an exact metadata filter — it
        fetches the complete content of a specific uploaded file rather than
        performing semantic ranking.

        Args:
            file_id:  UUID hex prefix of the stored filename.
            category: Which collection to query.

        Returns:
            List of dicts with keys: text, source_file, page_number, chunk_index.
            Empty list when the file has not been indexed yet.
        """
        collection_name = _collection_for_category(category)

        def _get() -> dict:
            collection = self._get_collection(collection_name)
            return collection.get(
                where={"file_id": {"$eq": file_id}},
                include=["documents", "metadatas"],
            )

        try:
            raw = await asyncio.to_thread(_get)
        except Exception as exc:
            logger.error(
                "ChromaDB get failed. collection=%s file_id=%s error=%s",
                collection_name, file_id, exc, exc_info=True,
            )
            raise RuntimeError(
                f"Failed to retrieve chunks for file_id='{file_id}'."
            ) from exc

        documents: list[str] = raw.get("documents") or []
        metadatas: list[dict] = raw.get("metadatas") or []

        results = [
            {
                "text": doc,
                "source_file": meta.get("source_file", ""),
                "page_number": int(meta.get("page_number", 0)),
                "chunk_index": int(meta.get("chunk_index", 0)),
            }
            for doc, meta in zip(documents, metadatas)
        ]

        logger.info(
            "File-scoped retrieval complete. file_id=%s collection=%s chunks=%d",
            file_id, collection_name, len(results),
        )
        return results

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def collection_stats(self, category: UploadCategory) -> dict[str, Any]:
        """Return basic stats for the given collection (count, metadata)."""
        name = _collection_for_category(category)
        col = self._get_collection(name)
        return {
            "collection": name,
            "document_count": col.count(),
        }


# ---------------------------------------------------------------------------
# Singleton factory (FastAPI dependency)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_vector_service() -> VectorService:
    """
    Return the application-wide ``VectorService`` singleton.

    Cached with ``lru_cache`` so the embedding model is loaded only once.
    Use this as a FastAPI dependency::

        from app.services.vector_service import get_vector_service
        from fastapi import Depends

        async def my_endpoint(vs: VectorService = Depends(get_vector_service)):
            ...
    """
    _settings = get_settings()
    provider = build_embedding_provider(_settings)
    service = VectorService(embedding_provider=provider, settings=_settings)
    logger.info(
        "VectorService initialised. provider=%s", _settings.embedding_provider
    )
    return service
