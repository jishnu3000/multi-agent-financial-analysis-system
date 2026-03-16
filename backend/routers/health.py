"""
Utility routes: health-check and root info.
"""

from datetime import datetime

from fastapi import APIRouter

from core.config import settings

router = APIRouter(tags=["utility"])


@router.get("/health")
async def health_check():
    """Return service health status.

    Returns:
        JSON with ``status``, ``timestamp``, and ``openai_configured``.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "openai_configured": bool(settings.OPENAI_API_KEY),
    }


@router.get("/")
async def root():
    """Return basic API metadata and available endpoint paths."""
    return {
        "message": "Multi-Agent Financial Analysis System API",
        "version": "1.0.0",
        "endpoints": {
            "register": "/register (POST)",
            "login": "/login (POST)",
            "analyze": "/analyze (POST)",
            "history": "/history (GET)",
            "download": "/download/{filename} (GET)",
            "health": "/health (GET)",
        },
    }
