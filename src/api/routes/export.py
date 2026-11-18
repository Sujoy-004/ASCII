"""Export API endpoints for client recording admission and media delivery."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    File,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from src.api.config import config
from src.api.jobs import ExportJobManager
from src.api.limiter import limiter
from src.api.security import (
    consume_download_token,
    get_trusted_client_ip,
    issue_download_token,
    verify_job_token,
    verify_turnstile_token,
)
from src.api.transcode import run_ffmpeg_transcode, validate_assembled_media

logger = logging.getLogger(__name__)
router = APIRouter(tags=["export"])


async def _execute_transcode_job(job_id: str) -> None:
    """Asynchronous background worker for FFmpeg transcoding and progress telemetry."""
    manager = ExportJobManager.get_instance()
    job = manager.get_job(job_id)
    if not job:
        return

    job_dir = manager.get_job_dir(job_id)
    input_path = job_dir / "input.webm"
    ext = "gif" if job.format == "gif" else "mp4"
    output_path = job_dir / f"output.{ext}"

    try:
        # Pre-flight container inspection per D-07
        validate_assembled_media(
            input_path=str(input_path),
            format=job.format,
            max_duration=job.duration,
        )

        # Run memory-bounded transcode
        await run_ffmpeg_transcode(
            job=job,
            input_path=str(input_path),
            output_path=str(output_path),
        )

        # Issue single-use short-lived download token per D-10
        download_token = issue_download_token(job_id)
        manager.complete_job(
            job_id=job_id,
            output_path=str(output_path),
            download_token=download_token,
        )
        logger.info("Transcode job %s completed successfully: %s", job_id, output_path)

    except Exception as exc:
        logger.exception("Transcode job %s failed: %s", job_id, exc)
        manager.fail_job(job_id, str(exc))


class ExportInitRequest(BaseModel):
    """Payload for initializing an export session."""

    format: str = Field(default="mp4", description="Output format: mp4 or gif")
    duration: float = Field(default=10.0, description="Target duration in seconds")
    fps: int = Field(default=30, description="Target frame rate")
    turnstile_token: str | None = Field(default=None, description="Cloudflare Turnstile token")


@router.post("/init")
@limiter.limit("3/5minutes")
async def init_export(
    request: Request,
    body: ExportInitRequest,
) -> dict[str, object]:
    """Admit a single export job and receive an ephemeral job token per D-02 and EXPORT-01."""
    fmt = body.format.lower().strip()
    if fmt not in {"mp4", "gif"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported export format '{fmt}'. Allowed formats: 'mp4', 'gif'.",
        )

    # Duration limit validation per D-07
    max_duration = config.max_gif_duration if fmt == "gif" else config.max_video_duration
    if body.duration <= 0 or body.duration > max_duration:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Invalid duration {body.duration}s for format '{fmt}'. "
                f"Must be between 0.1s and {max_duration}s."
            ),
        )

    # FPS validation
    max_fps = 15 if fmt == "gif" else 60
    if body.fps < 1 or body.fps > max_fps:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid FPS {body.fps} for format '{fmt}'. Must be between 1 and {max_fps}.",
        )

    client_ip = get_trusted_client_ip(request)

    # Cloudflare Turnstile bot verification per D-10
    is_valid_turnstile = await verify_turnstile_token(body.turnstile_token, client_ip)
    if not is_valid_turnstile:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cloudflare Turnstile verification failed. Please refresh and retry.",
        )

    manager = ExportJobManager.get_instance()
    job, job_token = await manager.acquire_job(
        format=fmt,
        duration=body.duration,
        fps=body.fps,
        client_ip=client_ip,
    )

    return {
        "job_id": job.id,
        "job_token": job_token,
        "state": job.state,
    }


@router.post("/{job_id}/chunk")
@limiter.limit("120/minute")
async def upload_chunk(
    request: Request,
    job_id: str,
    chunk_index: int = Query(..., ge=0),
    x_job_token: Annotated[str | None, Header(alias="X-Job-Token")] = None,
) -> dict[str, object]:
    """Accept sequential chunk binary uploads and stream to disk per D-01 and EXPORT-01."""
    manager = ExportJobManager.get_instance()
    job = manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    if not verify_job_token(x_job_token, job.token_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Job-Token header.",
        )

    if job.state not in {"capturing", "uploading"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot upload chunks when job is in state '{job.state}'.",
        )

    # Read binary stream directly from request body
    chunk_bytes = await request.body()
    chunk_len = len(chunk_bytes)

    # Individual chunk size check per D-07
    if chunk_len > config.max_chunk_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Chunk exceeds max allowable size of {config.max_chunk_bytes} bytes.",
        )

    # Cumulative upload ceiling per D-07
    max_total = (
        config.max_total_gif_bytes if job.format == "gif" else config.max_total_video_bytes
    )
    if job.total_uploaded_bytes + chunk_len > max_total:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Cumulative upload exceeds max ceiling of {max_total} bytes.",
        )

    job_dir = manager.get_job_dir(job_id)
    webm_path = job_dir / "input.webm"

    # Append chunk bytes to disk
    with open(webm_path, "ab") as f:
        f.write(chunk_bytes)

    job.total_uploaded_bytes += chunk_len
    job.uploaded_chunks += 1
    if job.state == "capturing":
        manager.transition_job(job_id, "uploading")

    return {
        "status": "chunk_received",
        "job_id": job.id,
        "chunk_index": chunk_index,
        "uploaded_bytes": job.total_uploaded_bytes,
    }


@router.post("/{job_id}/source-audio")
async def upload_source_audio(
    job_id: str,
    file: UploadFile = File(...),
    x_job_token: Annotated[str | None, Header(alias="X-Job-Token")] = None,
    x_clip_start: Annotated[float, Header(alias="X-Clip-Start")] = 0.0,
    x_clip_duration: Annotated[float, Header(alias="X-Clip-Duration")] = 0.0,
) -> dict[str, object]:
    """Upload source audio/video for server-side fallback seeking muxer per D-05."""
    manager = ExportJobManager.get_instance()
    job = manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    if not verify_job_token(x_job_token, job.token_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Job-Token header.",
        )

    job_dir = manager.get_job_dir(job_id)
    ext = Path(file.filename or "audio").suffix or ".mp4"
    audio_path = job_dir / f"source_audio{ext}"

    content = await file.read()
    with open(audio_path, "wb") as f:
        f.write(content)

    job.source_audio_path = str(audio_path)
    job.clip_start = max(0.0, x_clip_start)
    job.clip_duration = max(0.0, x_clip_duration)

    return {
        "status": "source_audio_received",
        "job_id": job.id,
        "size_bytes": len(content),
    }


@router.post("/{job_id}/finalize")
async def finalize_export(
    job_id: str,
    x_job_token: Annotated[str | None, Header(alias="X-Job-Token")] = None,
) -> dict[str, object]:
    """Transition job to encoding state for transcoding processing per D-02."""
    manager = ExportJobManager.get_instance()
    job = manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    if not verify_job_token(x_job_token, job.token_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Job-Token header.",
        )

    if job.state not in {"capturing", "uploading"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot finalize job in state '{job.state}'.",
        )

    manager.transition_job(job_id, "encoding")
    # Launch background transcoding task
    asyncio.create_task(_execute_transcode_job(job_id))

    return {
        "status": "finalized",
        "job_id": job.id,
        "state": job.state,
    }


@router.get("/{job_id}/status")
@limiter.limit("60/minute")
async def get_export_status(
    request: Request,
    job_id: str,
) -> dict[str, object]:
    """Return current job state and progress with container restart resilience per D-02."""
    manager = ExportJobManager.get_instance()
    job = manager.get_job(job_id)

    # Return HTTP 404 with expired state for unknown job ID per D-02
    if not job:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "state": "expired",
                "message": "Server instance restarted or job expired. Please retry.",
            },
        )

    res: dict[str, object] = {
        "job_id": job.id,
        "state": job.state,
        "progress": job.progress,
        "error": job.error,
    }
    if job.state == "completed" and job.download_token:
        res["download_token"] = job.download_token

    return res


@router.post("/{job_id}/cancel")
async def cancel_export(
    job_id: str,
    x_job_token: Annotated[str | None, Header(alias="X-Job-Token")] = None,
) -> dict[str, object]:
    """Cancel an active export job and release lock per D-02."""
    manager = ExportJobManager.get_instance()
    job = manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    if not verify_job_token(x_job_token, job.token_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Job-Token header.",
        )

    manager.cancel_job(job_id)
    return {
        "status": "cancelled",
        "job_id": job.id,
        "state": "cancelled",
    }


@router.get("/{job_id}/download")
async def download_export(
    job_id: str,
    download_token: str | None = Query(None),
) -> FileResponse:
    """Download generated media file using short-lived single-use download token per D-10."""
    manager = ExportJobManager.get_instance()
    job = manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    # Validate and consume single-use download token per D-10
    if not consume_download_token(job_id, download_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, missing, or expired download token.",
        )

    if job.state != "completed" or not job.output_path or not os.path.exists(job.output_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Export file is not ready or has been purged.",
        )

    media_type = "image/gif" if job.format == "gif" else "video/mp4"
    filename = f"export_{job_id[:8]}.{job.format}"

    return FileResponse(
        path=job.output_path,
        media_type=media_type,
        filename=filename,
    )


@router.post("/video")
async def export_video_compatibility(
    request: Request,
    body: ExportInitRequest,
) -> dict[str, object]:
    """Compatibility route routing to /api/export/init per EXPORT-01."""
    return await init_export(request, body)
