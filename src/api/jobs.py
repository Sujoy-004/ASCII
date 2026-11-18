"""Export job state machine and single-worker concurrency manager."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import secrets
import tempfile
import time
from typing import ClassVar

VALID_STATES = {
    "capturing",
    "uploading",
    "encoding",
    "completed",
    "failed",
    "cancelled",
    "expired",
}

TERMINAL_STATES = {
    "completed",
    "failed",
    "cancelled",
    "expired",
}


class ServerBusyError(RuntimeError):
    """Raised when server has an active export in progress or client has an active job."""

    def __init__(self, message: str = "Server is currently busy processing another export.", retry_after: int = 30) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class JobNotFoundError(KeyError):
    """Raised when the specified export job ID is not found."""


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal export job state transition is attempted."""


class InvalidTokenError(PermissionError):
    """Raised when job token validation fails."""


@dataclass
class ExportJob:
    """Represents an export job lifecycle and artifacts."""

    id: str
    token_hash: str
    format: str
    duration: float
    fps: int
    state: str
    created_at: float
    updated_at: float
    progress: float = 0.0
    download_token: str | None = None
    error: str | None = None
    client_ip: str = ""
    output_path: str | None = None
    source_audio_path: str | None = None
    clip_start: float = 0.0
    clip_duration: float = 0.0
    uploaded_chunks: int = 0
    total_uploaded_bytes: int = 0
    pid: int | None = None

    def is_active(self) -> bool:
        """Return True if job is currently active and occupying processing slots."""
        return self.state in {"capturing", "uploading", "encoding"}

    def is_terminal(self) -> bool:
        """Return True if job has reached a final state."""
        return self.state in TERMINAL_STATES


class ExportJobManager:
    """Manages process-local export jobs with asyncio concurrency locking."""

    _instance: ClassVar[ExportJobManager | None] = None

    def __init__(self, base_storage_dir: str | Path | None = None) -> None:
        self._lock = asyncio.Lock()
        self._jobs: dict[str, ExportJob] = {}
        self._active_job_id: str | None = None
        if base_storage_dir:
            self._storage_dir = Path(base_storage_dir)
        else:
            env_dir = os.environ.get("EXPORT_STORAGE_DIR")
            if env_dir:
                self._storage_dir = Path(env_dir)
            elif os.name != "nt" and os.path.exists("/tmp"):
                self._storage_dir = Path("/tmp/ascii_studio_exports")
            else:
                self._storage_dir = Path(tempfile.gettempdir()) / "ascii_studio_exports"
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_instance(cls) -> ExportJobManager:
        """Retrieve or create singleton manager instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def storage_dir(self) -> Path:
        """Return base storage directory."""
        return self._storage_dir

    def get_job_dir(self, job_id: str) -> Path:
        """Return job-specific directory on disk, ensuring it exists."""
        job_dir = self._storage_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        return job_dir

    def get_job(self, job_id: str) -> ExportJob | None:
        """Retrieve job by ID if present."""
        return self._jobs.get(job_id)

    def get_active_job(self) -> ExportJob | None:
        """Retrieve currently active job if any."""
        if self._active_job_id:
            return self._jobs.get(self._active_job_id)
        return None

    async def acquire_job(
        self,
        format: str,
        duration: float,
        fps: int = 30,
        client_ip: str = "",
    ) -> tuple[ExportJob, str]:
        """Admit a single export job under process-local lock per D-02 and EXPORT-01."""
        if self._lock.locked() or self._active_job_id is not None:
            raise ServerBusyError("Server is currently busy processing another export.", retry_after=30)

        # Enforce strictly 1 active job per client IP per D-10
        if client_ip:
            for job in self._jobs.values():
                if job.client_ip == client_ip and job.is_active():
                    raise ServerBusyError(
                        "An active export job is already in progress for this client.",
                        retry_after=30,
                    )

        await self._lock.acquire()
        job_id = secrets.token_hex(16)
        job_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(job_token.encode("utf-8")).hexdigest()
        now = time.time()

        job = ExportJob(
            id=job_id,
            token_hash=token_hash,
            format=format.lower(),
            duration=duration,
            fps=fps,
            state="capturing",
            created_at=now,
            updated_at=now,
            client_ip=client_ip,
        )

        self._jobs[job_id] = job
        self._active_job_id = job_id
        # Ensure job storage directory is created
        self.get_job_dir(job_id)

        return job, job_token

    def release_lock(self, job_id: str) -> None:
        """Release the concurrency lock for the specified job ID."""
        if self._active_job_id == job_id:
            self._active_job_id = None
            if self._lock.locked():
                self._lock.release()

    def transition_job(
        self,
        job_id: str,
        new_state: str,
        progress: float | None = None,
        error: str | None = None,
        output_path: str | None = None,
        download_token: str | None = None,
    ) -> ExportJob:
        """Transition job state and release lock if moving to terminal state."""
        job = self._jobs.get(job_id)
        if not job:
            raise JobNotFoundError(f"Export job {job_id} not found.")

        if new_state not in VALID_STATES:
            raise InvalidStateTransitionError(f"Invalid export state: {new_state}")

        job.state = new_state
        job.updated_at = time.time()

        if progress is not None:
            job.progress = max(0.0, min(1.0, progress))
        if error is not None:
            job.error = error
        if output_path is not None:
            job.output_path = output_path
        if download_token is not None:
            job.download_token = download_token

        if job.is_terminal():
            self.release_lock(job_id)

        return job

    def cancel_job(self, job_id: str, reason: str = "User cancelled export") -> ExportJob:
        """Cancel an in-progress export job and release lock."""
        return self.transition_job(job_id, "cancelled", error=reason)

    def fail_job(self, job_id: str, error_message: str) -> ExportJob:
        """Fail an export job with an error message and release lock."""
        return self.transition_job(job_id, "failed", error=error_message)

    def complete_job(
        self,
        job_id: str,
        output_path: str,
        download_token: str | None = None,
    ) -> ExportJob:
        """Mark an export job as successfully completed."""
        return self.transition_job(
            job_id,
            "completed",
            progress=1.0,
            output_path=output_path,
            download_token=download_token,
        )

    def reset(self) -> None:
        """Reset manager state for hermetic testing."""
        if self._lock.locked():
            self._lock.release()
        self._jobs.clear()
        self._active_job_id = None
