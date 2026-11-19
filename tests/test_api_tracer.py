"""Hermetic integration tests for the FastAPI tracer path."""

from __future__ import annotations

import os
import tempfile
import pytest
from httpx import ASGITransport, AsyncClient

from src.api.jobs import ExportJobManager
from src.api.limiter import limiter
from src.api.main import app
from src.api.security import issue_download_token, reset_security_state


@pytest.fixture(autouse=True)
def clean_job_manager():
    """Reset job manager, rate limiter, and security token state before each test."""
    manager = ExportJobManager.get_instance()
    manager.reset()
    limiter.reset()
    reset_security_state()
    yield
    manager.reset()
    limiter.reset()
    reset_security_state()


@pytest.mark.asyncio
async def test_health_check():
    """GET /api/health returns 200 OK with status: ok for container pre-warming."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "1.0.0"
        assert "timestamp" in data
        assert isinstance(data["timestamp"], float)


@pytest.mark.asyncio
async def test_export_init_and_concurrency_lock():
    """POST /api/export/init acquires lock and rejects concurrent calls with HTTP 503."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # First export job admission
        init_payload = {"format": "mp4", "duration": 10.0, "fps": 30}
        resp = await client.post("/api/export/init", json=init_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data
        assert len(data["job_id"]) == 32  # 16 bytes in hex
        assert "job_token" in data
        assert len(data["job_token"]) > 20
        assert data["state"] == "capturing"
        job_id = data["job_id"]

        # Concurrent export job attempt while first is active -> HTTP 503
        concurrent_resp = await client.post("/api/export/init", json=init_payload)
        assert concurrent_resp.status_code == 503
        assert concurrent_resp.headers.get("retry-after") == "30"
        err_data = concurrent_resp.json()
        assert err_data["error"] == "server_busy"
        assert err_data["retry_after"] == 30

        # Cancel active job to verify lock release
        cancel_resp = await client.post(
            f"/api/export/{job_id}/cancel",
            headers={"X-Job-Token": data["job_token"]},
        )
        assert cancel_resp.status_code == 200

        # Now another job can be admitted
        resp_after = await client.post("/api/export/init", json=init_payload)
        assert resp_after.status_code == 200


@pytest.mark.asyncio
async def test_chunk_upload_and_finalize_flow():
    """POST /api/export/{id}/chunk streams binary to disk and finalize transitions to encoding."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        init_resp = await client.post(
            "/api/export/init",
            json={"format": "mp4", "duration": 5.0, "fps": 30},
        )
        assert init_resp.status_code == 200
        init_data = init_resp.json()
        job_id = init_data["job_id"]
        job_token = init_data["job_token"]

        # Chunk upload without token -> 401 Unauthorized
        chunk1 = b"RIFF\x00\x00\x00\x00WEBMmockchunk1"
        bad_token_resp = await client.post(
            f"/api/export/{job_id}/chunk?chunk_index=0",
            content=chunk1,
            headers={"Content-Type": "application/octet-stream"},
        )
        assert bad_token_resp.status_code == 401

        # Chunk upload with valid token -> 200 OK
        chunk_resp = await client.post(
            f"/api/export/{job_id}/chunk?chunk_index=0",
            content=chunk1,
            headers={
                "Content-Type": "application/octet-stream",
                "X-Job-Token": job_token,
            },
        )
        assert chunk_resp.status_code == 200
        chunk_data = chunk_resp.json()
        assert chunk_data["status"] == "chunk_received"
        assert chunk_data["chunk_index"] == 0
        assert chunk_data["uploaded_bytes"] == len(chunk1)

        # Check job state transitioned from capturing to uploading
        status_resp = await client.get(f"/api/export/{job_id}/status")
        assert status_resp.status_code == 200
        assert status_resp.json()["state"] == "uploading"

        # Finalize export job -> 200 OK and state: encoding
        finalize_resp = await client.post(
            f"/api/export/{job_id}/finalize",
            headers={"X-Job-Token": job_token},
        )
        assert finalize_resp.status_code == 200
        assert finalize_resp.json()["state"] == "encoding"

        # Check status reflects encoding
        status_resp2 = await client.get(f"/api/export/{job_id}/status")
        assert status_resp2.status_code == 200
        assert status_resp2.json()["state"] == "encoding"


@pytest.mark.asyncio
async def test_unknown_job_status_returns_404_expired():
    """GET /api/export/{id}/status for unknown job ID returns HTTP 404 with state expired per D-02."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/export/0123456789abcdef0123456789abcdef/status")
        assert resp.status_code == 404
        data = resp.json()
        assert data["state"] == "expired"
        assert "Server instance restarted or job expired" in data["message"]


@pytest.mark.asyncio
async def test_download_flow_with_token():
    """GET /api/export/{id}/download requires short-lived download token and serves file."""
    manager = ExportJobManager.get_instance()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create job directly
        job, job_token = await manager.acquire_job(format="mp4", duration=5.0)

        # Create temporary dummy file as output
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom")
            temp_path = f.name

        try:
            download_token = issue_download_token(job.id, ttl_seconds=300)
            manager.complete_job(job.id, output_path=temp_path, download_token=download_token)

            # Download without token -> 401
            resp_no_token = await client.get(f"/api/export/{job.id}/download")
            assert resp_no_token.status_code == 401

            # Download with bad token -> 401
            resp_bad_token = await client.get(f"/api/export/{job.id}/download?download_token=wrong")
            assert resp_bad_token.status_code == 401

            # Download with valid token -> 200 OK FileResponse
            resp_good = await client.get(
                f"/api/export/{job.id}/download?download_token={download_token}"
            )
            assert resp_good.status_code == 200
            assert resp_good.headers["content-type"] == "video/mp4"
            assert f"export_{job.id[:8]}.mp4" in resp_good.headers.get("content-disposition", "")
            assert resp_good.content == b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"

            # Single-use: consuming again must return 401
            resp_second = await client.get(
                f"/api/export/{job.id}/download?download_token={download_token}"
            )
            assert resp_second.status_code == 401
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


@pytest.mark.asyncio
async def test_compatibility_video_route():
    """POST /api/export/video compatibility route successfully routes to export init."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/export/video",
            json={"format": "mp4", "duration": 5.0, "fps": 30},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data
        assert "job_token" in data
        assert data["state"] == "capturing"
