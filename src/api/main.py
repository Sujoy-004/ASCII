"""FastAPI application entry point for RGB ASCII & Retro FX Studio."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.api.config import config
from src.api.janitor import ExportJanitor
from src.api.jobs import ExportJobManager, ServerBusyError
from src.api.limiter import limiter
from src.api.routes.export import router as export_router
from src.api.routes.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan: start storage janitor on boot, terminate on shutdown."""
    storage_dir = ExportJobManager.get_instance().storage_dir
    janitor = ExportJanitor(storage_dir=storage_dir, sweep_interval=60)
    task = asyncio.create_task(janitor.start())
    yield
    await janitor.stop()
    task.cancel()


app = FastAPI(
    title="RGB ASCII & Retro FX Studio API",
    version="0.1.0",
    description="Production backend API for high-resolution video and animated GIF export.",
    lifespan=lifespan,
)

# Connect SlowAPI rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]


@app.exception_handler(ServerBusyError)
async def server_busy_handler(request: Request, exc: ServerBusyError) -> JSONResponse:
    """Return HTTP 503 with Retry-After: 30 header when export concurrency lock is active per D-02."""
    return JSONResponse(
        status_code=503,
        content={
            "error": "server_busy",
            "retry_after": exc.retry_after,
            "message": str(exc),
        },
        headers={"Retry-After": str(exc.retry_after)},
    )


# Hardened production CORS per D-09
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_origin_regex=config.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "X-Job-Token",
        "X-Turnstile-Token",
        "X-Clip-Start",
        "X-Clip-Duration",
    ],
    expose_headers=[
        "Content-Disposition",
        "Content-Length",
        "Retry-After",
        "X-Job-Token",
    ],
)

# Route inclusion
app.include_router(health_router, prefix="/api")
app.include_router(export_router, prefix="/api/export")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)
