"""Token store backed by Redis."""

import json
import secrets

import redis.asyncio as redis

from app.config import settings

_redis: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def store_token(context: dict) -> str:
    """Generate a random token, store context in Redis, return the token."""
    token = secrets.token_urlsafe(32)
    r = await get_redis()
    await r.setex(f"token:{token}", settings.token_ttl, json.dumps(context))
    return token


async def get_token_context(token: str) -> dict | None:
    """Look up a token and return its context, or None if expired/invalid."""
    r = await get_redis()
    data = await r.get(f"token:{token}")
    if data is None:
        return None
    return json.loads(data)
