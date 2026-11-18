"""Rate limiter instance for FastAPI ingress defense."""

from __future__ import annotations

from slowapi import Limiter
from src.api.security import get_trusted_client_ip

# Single SlowAPI limiter instance using trusted client IP
limiter = Limiter(key_func=get_trusted_client_ip)
