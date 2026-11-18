"""Comprehensive hermetic tests for ingress security, Cloudflare CIDRs, and rate limiting."""

from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, patch
from fastapi import Request
import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from src.api.config import config
from src.api.jobs import ExportJobManager
from src.api.limiter import limiter
from src.api.main import app
from src.api.security import (
    consume_download_token,
    get_trusted_client_ip,
    issue_download_token,
    reset_security_state,
    verify_job_token,
    verify_turnstile_token,
)


@pytest.fixture(autouse=True)
def clean_security_state():
    """Reset manager, limiter, and security state between tests."""
    manager = ExportJobManager.get_instance()
    manager.reset()
    limiter.reset()
    reset_security_state()
    yield
    manager.reset()
    limiter.reset()
    reset_security_state()


def test_trusted_client_ip_with_cloudflare_cidr():
    """Cloudflare connection IP allows trusting CF-Connecting-IP; non-CF IP ignores it."""
    # Dummy mock request helper
    def make_mock_request(client_host: str, headers: dict[str, str]) -> Request:
        scope = {
            "type": "http",
            "client": (client_host, 12345),
            "headers": [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in headers.items()],
        }
        return Request(scope)

    # 1. Direct Cloudflare IPv4 IP (173.245.48.10 is in 173.245.48.0/20)
    cf_req = make_mock_request(
        client_host="173.245.48.10",
        headers={"CF-Connecting-IP": "198.51.100.5"},
    )
    assert get_trusted_client_ip(cf_req) == "198.51.100.5"

    # 2. Direct Cloudflare IPv6 IP (2606:4700::1 is in 2606:4700::/32)
    cf_v6_req = make_mock_request(
        client_host="2606:4700::1",
        headers={"CF-Connecting-IP": "203.0.113.42"},
    )
    assert get_trusted_client_ip(cf_v6_req) == "203.0.113.42"

    # 3. Spoofed request from arbitrary public IP (192.0.2.1 is TEST-NET-1, not Cloudflare)
    spoof_req = make_mock_request(
        client_host="192.0.2.1",
        headers={
            "CF-Connecting-IP": "8.8.8.8",
            "X-Forwarded-For": "8.8.8.8, 192.0.2.1",
        },
    )
    # Must NOT trust spoofed CF-Connecting-IP or X-Forwarded-For; must return client socket IP
    assert get_trusted_client_ip(spoof_req) == "192.0.2.1"


def test_constant_time_token_verification():
    """verify_job_token uses constant-time digest comparison."""
    secret_token = "secure_random_urlsafe_token_123456789"
    stored_hash = hashlib.sha256(secret_token.encode("utf-8")).hexdigest()

    assert verify_job_token(secret_token, stored_hash) is True
    assert verify_job_token("wrong_token", stored_hash) is False
    assert verify_job_token("", stored_hash) is False
    assert verify_job_token(None, stored_hash) is False
    assert verify_job_token(secret_token, "wrong_hash") is False


def test_download_token_single_use_and_expiration():
    """Download tokens expire after TTL and are strictly single-use."""
    job_id = "test_job_123"

    # 1. Single-use test
    token = issue_download_token(job_id, ttl_seconds=300)
    assert consume_download_token(job_id, token) is True
    # Second consumption must fail
    assert consume_download_token(job_id, token) is False

    # 2. Mismatched job ID
    token2 = issue_download_token(job_id, ttl_seconds=300)
    assert consume_download_token("other_job_456", token2) is False

    # 3. Expired token (TTL = 0.01 seconds)
    token_exp = issue_download_token(job_id, ttl_seconds=-1)  # already expired
    assert consume_download_token(job_id, token_exp) is False


@pytest.mark.asyncio
async def test_turnstile_verification_flow():
    """verify_turnstile_token bypasses in dev, verifies via HTTP in production."""
    # In dev mode, always returns True
    assert await verify_turnstile_token(None, "127.0.0.1") is True
    assert await verify_turnstile_token("any_token", "127.0.0.1") is True

    # Test production mode with mocked HTTP client
    original_env = config.environment
    original_secret = config.turnstile_secret_key
    try:
        config.environment = "production"
        config.turnstile_secret_key = "0x4AAAAAAtestsecret"
        config.turnstile_disabled = False

        # Missing token in prod -> False
        assert await verify_turnstile_token(None, "127.0.0.1") is False
        assert await verify_turnstile_token("", "127.0.0.1") is False

        # Mock successful Turnstile API call
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = httpx.Response(200, json={"success": True})

            assert await verify_turnstile_token("valid_token", "198.51.100.1") is True

        # Mock rejected Turnstile API call
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = httpx.Response(200, json={"success": False, "error-codes": ["invalid-input-response"]})

            assert await verify_turnstile_token("invalid_token", "198.51.100.1") is False
    finally:
        config.environment = original_env
        config.turnstile_secret_key = original_secret
        config.turnstile_disabled = False


@pytest.mark.asyncio
async def test_slowapi_rate_limiting():
    """SlowAPI limits init requests to 3 per 5 minutes per client IP."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Client IP 192.0.2.55 sends requests
        headers = {"Client-IP": "192.0.2.55"}

        for i in range(3):
            resp = await client.post(
                "/api/export/init",
                json={"format": "mp4", "duration": 5.0, "fps": 30},
                headers=headers,
            )
            assert resp.status_code == 200, f"Request {i+1} failed"
            # Cancel immediately so lock is released for next rate-limit hit
            job_id = resp.json()["job_id"]
            job_token = resp.json()["job_token"]
            cancel_resp = await client.post(
                f"/api/export/{job_id}/cancel",
                headers={"X-Job-Token": job_token},
            )
            assert cancel_resp.status_code == 200

        # 4th request must be rate-limited with HTTP 429
        rate_limited_resp = await client.post(
            "/api/export/init",
            json={"format": "mp4", "duration": 5.0, "fps": 30},
            headers=headers,
        )
        assert rate_limited_resp.status_code == 429
        assert "Rate limit exceeded" in rate_limited_resp.text


@pytest.mark.asyncio
async def test_cors_headers():
    """CORS middleware returns configured allowed and exposed headers per D-09."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Preflight OPTIONS request
        resp = await client.options(
            "/api/export/init",
            headers={
                "Origin": "https://rgb-ascii.pages.dev",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type, X-Job-Token, X-Turnstile-Token",
            },
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "https://rgb-ascii.pages.dev"
        assert "X-Job-Token" in resp.headers.get("access-control-allow-headers", "")

        # Actual GET request exposes configured headers
        get_resp = await client.get(
            "/api/health",
            headers={"Origin": "https://rgb-ascii.pages.dev"},
        )
        assert get_resp.status_code == 200
        assert get_resp.headers.get("access-control-allow-origin") == "https://rgb-ascii.pages.dev"
        expose_headers = get_resp.headers.get("access-control-expose-headers", "")
        assert "Retry-After" in expose_headers
        assert "X-Job-Token" in expose_headers
