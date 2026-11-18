"""Health check router for Render pre-warming and container status."""

from __future__ import annotations

import time
from fastapi import APIRouter, Request

from src.api.limiter import limiter

router = APIRouter(tags=["health"])


@router.get("/health")
@limiter.limit("30/minute")
async def health_check(request: Request) -> dict[str, object]:
    """Return health status and current timestamp for container pre-warming."""
    return {
        "status": "ok",
        "version": "0.1.0",
        "timestamp": time.time(),
    }
