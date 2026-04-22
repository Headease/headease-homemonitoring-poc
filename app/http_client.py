"""Shared httpx client factory with request/response logging."""

import logging
import ssl

import httpx

from app.config import settings

logger = logging.getLogger("headease.http")


async def _log_request(request: httpx.Request):
    body = request.content.decode("utf-8", errors="replace") if request.content else ""
    logger.info(">>> %s %s", request.method, request.url)
    if body and len(body) < 2000:
        logger.info(">>> Body: %s", body)


async def _log_response(response: httpx.Response):
    await response.aread()
    body = response.text[:500] if response.text else ""
    logger.info("<<< %s %s", response.status_code, response.url)
    if body:
        logger.info("<<< Body: %s", body)


def get_ssl_context() -> ssl.SSLContext:
    """SSL context using LDN cert chain for mTLS."""
    ctx = ssl.create_default_context()
    ctx.load_cert_chain(certfile=settings.ldn_chain_cert_path, keyfile=settings.client_key_path)
    return ctx


def create_client(**kwargs) -> httpx.AsyncClient:
    """Create an httpx.AsyncClient with mTLS and request logging."""
    kwargs.setdefault("verify", get_ssl_context())
    kwargs.setdefault("timeout", 30)
    kwargs.setdefault("event_hooks", {"request": [_log_request], "response": [_log_response]})
    return httpx.AsyncClient(**kwargs)
