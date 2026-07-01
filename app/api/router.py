"""
Top-level API router — mounts all versioned sub-routers.

Centralising version mounting here makes it trivial to add /v2
without touching main.py.
"""

from fastapi import APIRouter

from app.api.v1.router import api_v1_router

api_router = APIRouter(prefix="/api")

api_router.include_router(api_v1_router)
