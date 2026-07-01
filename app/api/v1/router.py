"""
API v1 router — aggregates all v1 endpoint routers.

Add new endpoint modules here as the API grows.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import ai, uploads

api_v1_router = APIRouter(prefix="/v1")

api_v1_router.include_router(uploads.router)
api_v1_router.include_router(ai.router)
