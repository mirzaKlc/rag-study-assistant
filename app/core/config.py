"""
Application configuration management using pydantic-settings.

All environment variables are loaded from the .env file and validated
at startup. Accessing a missing required variable raises a clear error.
"""

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Type-safe application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_name: str = Field(default="OzetAI", description="Application display name")
    app_version: str = Field(default="1.0.0")
    environment: str = Field(default="development")
    port: int = Field(default=8000)
    debug: bool = Field(default=False)

    # --- Security ---
    secret_key: str = Field(default="CHANGE_ME_IN_PRODUCTION")
    allowed_origins: str = Field(default="http://localhost:3000")

    # --- Google Gemini ---
    gemini_api_key: str = Field(description="Google Gemini API key")
    gemini_model: str = Field(default="gemini-2.5-flash")
    gemini_summary_temperature: float = Field(default=0.4, ge=0.0, le=2.0)
    gemini_question_temperature: float = Field(default=0.8, ge=0.0, le=2.0)

    # --- AI Retrieval ---
    retrieval_top_k: int = Field(default=15, ge=1, le=100)
    max_context_chars: int = Field(default=50_000, ge=1000)

    # --- Vector Database ---
    chroma_db_path: str = Field(default="./chroma_db")
    chroma_collection_name: str = Field(default="ozetai_documents")

    # --- Text Chunking ---
    chunk_size: int = Field(default=1000, ge=100, le=8000)
    chunk_overlap: int = Field(default=200, ge=0)

    # --- Embedding ---
    # "sentence_transformer" | "gemini"
    embedding_provider: str = Field(default="sentence_transformer")
    embedding_model: str = Field(default="all-MiniLM-L6-v2")

    # --- File Upload ---
    upload_dir: str = Field(default="./uploads")
    max_upload_size_mb: int = Field(default=50)
    allowed_extensions: str = Field(default="pdf,txt")

    # --- Logging ---
    log_level: str = Field(default="INFO")
    log_file: str = Field(default="./logs/app.log")

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v.lower() not in allowed:
            raise ValueError(f"environment must be one of: {allowed}")
        return v.lower()

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in allowed:
            raise ValueError(f"log_level must be one of: {allowed}")
        return v.upper()

    @field_validator("embedding_provider")
    @classmethod
    def validate_embedding_provider(cls, v: str) -> str:
        allowed = {"sentence_transformer", "gemini"}
        if v.lower() not in allowed:
            raise ValueError(f"embedding_provider must be one of: {allowed}")
        return v.lower()

    @property
    def allowed_extensions_list(self) -> List[str]:
        """Return allowed file extensions as a list of lowercase strings."""
        return [ext.strip().lower() for ext in self.allowed_extensions.split(",")]

    @property
    def allowed_origins_list(self) -> List[str]:
        """Return CORS allowed origins as a list."""
        return [origin.strip() for origin in self.allowed_origins.split(",")]

    @property
    def max_upload_size_bytes(self) -> int:
        """Return max upload size in bytes."""
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def content_upload_dir(self) -> Path:
        return Path(self.upload_dir) / "content"

    @property
    def exams_upload_dir(self) -> Path:
        return Path(self.upload_dir) / "exams"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached singleton Settings instance."""
    return Settings()
