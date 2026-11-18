"""Ephemeral storage lifecycle manager with active PID and state protection."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
import shutil
import time

import psutil

from src.api.config import config
from src.api.jobs import ExportJobManager

logger = logging.getLogger(__name__)


class ExportJanitor:
    """Manages ephemeral disk quota and sweeps expired export directories per D-08."""

    def __init__(
        self,
        storage_dir: Path | str | None = None,
        sweep_interval: int = 60,
    ) -> None:
        if storage_dir:
            self._storage_dir = Path(storage_dir)
        else:
            self._storage_dir = ExportJobManager.get_instance().storage_dir
        self.sweep_interval = sweep_interval
        self._running = False
        self._task: asyncio.Task[None] | None = None

    @property
    def storage_dir(self) -> Path:
        """Return base directory monitored by janitor."""
        return self._storage_dir

    def calculate_storage_usage(self) -> int:
        """Calculate total disk usage in bytes across the storage directory."""
        total_size = 0
        if not self._storage_dir.exists():
            return 0
        for entry in self._storage_dir.rglob("*"):
            if entry.is_file():
                try:
                    total_size += entry.stat().st_size
                except OSError:
                    pass
        return total_size

    def is_pid_active(self, pid: int | None) -> bool:
        """Check whether the OS process table contains the specified PID per D-08."""
        if not pid or pid <= 0:
            return False
        try:
            return psutil.pid_exists(pid)
        except Exception:
            return False

    async def run_sweep(self) -> dict[str, int]:
        """Perform one pass of active-state protected storage sweeping per D-08."""
        if not self._storage_dir.exists():
            return {"purged_jobs": 0, "freed_bytes": 0}

        manager = ExportJobManager.get_instance()
        now = time.time()
        purged_count = 0
        freed_bytes = 0

        # Measure current total storage consumption
        total_disk_usage = self.calculate_storage_usage()
        # High watermark trigger (400 MB towards 500 MB quota ceiling) per D-08
        urgent_purge = total_disk_usage > 400 * 1024 * 1024

        # Inactivity timeout check for active upload jobs (60s without chunks) per D-08
        for job in list(manager._jobs.values()):
            if job.state in {"capturing", "uploading"}:
                if now - job.updated_at > config.inactivity_timeout_seconds:
                    logger.warning("Job %s timed out due to upload inactivity (60s)", job.id)
                    manager.fail_job(job.id, "Upload inactivity timeout exceeded (60s)")

        for child in self._storage_dir.iterdir():
            if not child.is_dir():
                continue

            job_id = child.name
            job = manager.get_job(job_id)

            # Active Process Protection: strictly NEVER purge active jobs or living PIDs per D-08
            if job and job.is_active():
                continue
            if job and self.is_pid_active(job.pid):
                continue

            # Check age of directory on disk
            try:
                mtime = child.stat().st_mtime
                age_seconds = now - mtime
            except OSError:
                age_seconds = 0

            should_purge = False

            if job:
                if job.state == "completed":
                    # Urgent purge: completed jobs older than 2 min when disk usage > 400 MB per D-08
                    if urgent_purge and age_seconds > 120:
                        should_purge = True
                    # Normal retention: 10 minutes post-completion per D-08
                    elif age_seconds > config.max_job_lifetime_seconds:
                        should_purge = True
                elif job.is_terminal() and age_seconds > config.max_job_lifetime_seconds:
                    should_purge = True
            else:
                # Orphan directory from previous server instance/crash
                if age_seconds > config.max_job_lifetime_seconds:
                    should_purge = True

            if should_purge:
                dir_size = 0
                for f in child.rglob("*"):
                    if f.is_file():
                        try:
                            dir_size += f.stat().st_size
                        except OSError:
                            pass
                shutil.rmtree(child, ignore_errors=True)
                purged_count += 1
                freed_bytes += dir_size
                if job and job.state != "expired":
                    try:
                        manager.transition_job(job_id, "expired")
                    except Exception:
                        pass
                logger.info("Janitor purged directory for job %s (freed %d bytes)", job_id, dir_size)

        return {"purged_jobs": purged_count, "freed_bytes": freed_bytes}

    async def start(self) -> None:
        """Start periodic background janitor sweeper loop."""
        self._running = True
        logger.info("Storage janitor started with sweep interval %ds", self.sweep_interval)
        try:
            while self._running:
                await self.run_sweep()
                await asyncio.sleep(self.sweep_interval)
        except asyncio.CancelledError:
            self._running = False
            logger.info("Storage janitor task cancelled.")

    async def stop(self) -> None:
        """Stop periodic background janitor sweeper loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
