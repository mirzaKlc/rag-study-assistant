"""
Centralized logging configuration for the application.

Sets up a structured logger that writes to both stdout and a rotating
file handler. Call configure_logging() once at application startup.
"""

import logging
import logging.handlers
import sys
from pathlib import Path

from app.core.config import get_settings


def configure_logging() -> None:
    """Configure the root logger with console and file handlers."""
    settings = get_settings()

    log_dir = Path(settings.log_file).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    log_level = getattr(logging, settings.log_level, logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # Rotating file handler — 10 MB per file, keeps last 5
    file_handler = logging.handlers.RotatingFileHandler(
        filename=settings.log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Silence noisy third-party loggers in production
    if get_settings().is_production:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "Logging configured. level=%s env=%s",
        settings.log_level,
        settings.environment,
    )


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Use __name__ as the argument."""
    return logging.getLogger(name)
