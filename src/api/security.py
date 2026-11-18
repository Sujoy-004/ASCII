"""Ingress abuse defense, Cloudflare CIDR extraction, and token verification."""

from __future__ import annotations

import hashlib
import ipaddress
import secrets
import time
from typing import TYPE_CHECKING
import httpx

from src.api.config import config

if TYPE_CHECKING:
    from fastapi import Request

# Published Cloudflare IP CIDRs (https://www.cloudflare.com/ips/)
CLOUDFLARE_NETWORKS: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    ipaddress.ip_network(cidr)
    for cidr in [
        "173.245.48.0/20",
        "103.21.244.0/22",
        "103.22.200.0/22",
        "103.31.4.0/22",
        "141.101.64.0/18",
        "108.162.192.0/18",
        "190.93.240.0/20",
        "188.114.96.0/20",
        "197.234.240.0/22",
        "198.41.128.0/17",
        "162.158.0.0/15",
        "104.16.0.0/13",
        "104.24.0.0/14",
        "172.64.0.0/13",
        "131.0.72.0/22",
        "2400:cb00::/32",
        "2606:4700::/32",
        "2803:f800::/32",
        "2405:b500::/32",
        "2405:8100::/32",
        "2a06:98c0::/29",
        "2c0f:f248::/32",
    ]
]


def get_trusted_client_ip(request: Request) -> str:
    """Validate client connection IP against Cloudflare CIDRs before trusting CF-Connecting-IP per D-10."""
    direct_ip_str = request.client.host if request.client else "127.0.0.1"
    try:
        direct_ip = ipaddress.ip_address(direct_ip_str)
        is_cf = any(direct_ip in net for net in CLOUDFLARE_NETWORKS)
    except ValueError:
        is_cf = False

    if is_cf:
        cf_ip = request.headers.get("CF-Connecting-IP")
        if cf_ip:
            return cf_ip.strip()
    return direct_ip_str


async def verify_turnstile_token(token: str | None, client_ip: str) -> bool:
    """Verify Cloudflare Turnstile token via siteverify endpoint per D-10."""
    if config.turnstile_disabled or config.environment == "development":
        return True

    if not token or not token.strip():
        return False

    url = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    data = {
        "secret": config.turnstile_secret_key,
        "response": token.strip(),
        "remoteip": client_ip,
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, data=data)
            if resp.status_code != 200:
                return False
            result = resp.json()
            return bool(result.get("success", False))
    except Exception:
        return False


def hash_token(token: str) -> str:
    """Compute SHA-256 hex digest of an authentication token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_job_token(header_token: str | None, stored_hash: str) -> bool:
    """Validate incoming X-Job-Token using constant-time comparison per D-10."""
    if not header_token or not stored_hash:
        return False
    computed_hash = hash_token(header_token)
    return secrets.compare_digest(computed_hash, stored_hash)


# In-memory single-use download token store: token -> (job_id, expiry_timestamp)
_download_tokens: dict[str, tuple[str, float]] = {}


def issue_download_token(job_id: str, ttl_seconds: int = 300) -> str:
    """Issue a short-lived (5 min default) single-use download token per D-10."""
    token = secrets.token_urlsafe(24)
    expiry = time.time() + ttl_seconds
    _download_tokens[token] = (job_id, expiry)
    return token


def consume_download_token(job_id: str, token: str | None) -> bool:
    """Validate and consume a single-use download token per D-10."""
    if not token:
        return False

    now = time.time()
    record = _download_tokens.pop(token, None)
    if record is None:
        return False

    token_job_id, expiry = record
    if now > expiry:
        return False

    return secrets.compare_digest(token_job_id, job_id)


def reset_security_state() -> None:
    """Reset security module state for hermetic testing."""
    _download_tokens.clear()
