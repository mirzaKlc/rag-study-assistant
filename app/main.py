"""
FastAPI application factory.

Responsibilities:
  - Create and configure the FastAPI instance
  - Register CORS middleware
  - Register global exception handlers
  - Mount the versioned API router
  - Expose a health-check endpoint
"""

import logging
import traceback
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.models.schemas import ErrorDetail, HealthResponse

# Configure logging before anything else
configure_logging()
logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown hooks
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Run startup and shutdown logic around the request loop."""
    logger.info(
        "Starting %s v%s [%s]",
        settings.app_name,
        settings.app_version,
        settings.environment,
    )

    # Ensure upload directories exist on every startup
    settings.content_upload_dir.mkdir(parents=True, exist_ok=True)
    settings.exams_upload_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Upload directories ready.")

    yield  # ← application runs here

    logger.info("Shutting down %s.", settings.app_name)


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    """Instantiate and fully configure the FastAPI application."""

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "RAG-powered study assistant API. "
            "Upload course materials and past exams; generate targeted questions."
        ),
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    _register_middleware(app)
    _register_exception_handlers(app)
    _register_routers(app)

    return app


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

def _register_middleware(app: FastAPI) -> None:
    """Attach all middleware to the application."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    logger.debug("CORS middleware registered. origins=%s", settings.allowed_origins_list)


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

def _register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers for a consistent error envelope."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """Convert FastAPI/Starlette HTTP exceptions to the standard ErrorDetail shape."""
        logger.warning(
            "HTTP %d on %s %s — %s",
            exc.status_code,
            request.method,
            request.url.path,
            exc.detail,
        )
        error = ErrorDetail(
            status_code=exc.status_code,
            detail=str(exc.detail),
            path=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error.model_dump(mode="json"),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Return structured 422 responses for Pydantic / query-param validation errors."""
        messages = "; ".join(
            f"{' → '.join(str(loc) for loc in err['loc'])}: {err['msg']}"
            for err in exc.errors()
        )
        logger.info(
            "Validation error on %s %s — %s",
            request.method,
            request.url.path,
            messages,
        )
        error = ErrorDetail(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=messages,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error.model_dump(mode="json"),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all handler — logs the full traceback, returns a safe 500 to the client."""
        logger.error(
            "Unhandled exception on %s %s\n%s",
            request.method,
            request.url.path,
            traceback.format_exc(),
        )
        error = ErrorDetail(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected internal error occurred. Please try again later.",
            path=request.url.path,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error.model_dump(mode="json"),
        )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

def _register_routers(app: FastAPI) -> None:
    """Mount the versioned API router and built-in utility endpoints."""

    app.include_router(api_router)

    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["System"],
        summary="Health check",
    )
    async def health_check() -> HealthResponse:
        """Returns 200 when the service is up. Used by load-balancers and uptime monitors."""
        return HealthResponse(
            status="ok",
            version=settings.app_version,
            environment=settings.environment,
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

app = create_app()
