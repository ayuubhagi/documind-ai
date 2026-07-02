"""Rate limiting via slowapi.

Authenticated requests are limited per user (so one abusive account can't
exhaust a shared IP's budget, and NAT'd users don't share a bucket); anonymous
requests fall back to the client IP. Limits use in-memory storage, which is
correct for a single-process deployment; swap in a Redis storage backend if
the API ever runs with multiple workers.
"""

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.security import decode_access_token


def rate_limit_key(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        user_id = decode_access_token(auth.removeprefix("Bearer "))
        if user_id is not None:
            return f"user:{user_id}"
    return get_remote_address(request)


limiter = Limiter(key_func=rate_limit_key, enabled=settings.RATE_LIMIT_ENABLED)
