"""FHIR API proxy — forwards to HAPI FHIR server after Bearer token check."""

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.config import settings
from app.token_store import get_token_context

logger = logging.getLogger("headease.fhir_proxy")

router = APIRouter()

REQUIRED_HEADERS = [
    "x-ura-identifier",
    "x-healthcareproviderroletype",
    "x-dezi-identifier",
    "x-dezi-roletype",
]

HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length",
    # httpx auto-decompresses, so these headers no longer describe the body we return
    "content-encoding",
}


async def verify_authorization(request: Request):
    """Verify authorization via Bearer token (Redis) or fallback to required headers."""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        context = await get_token_context(token)
        if context is None:
            raise HTTPException(status_code=401, detail="Invalid or expired Bearer token")
        request.state.token_context = context
        return

    missing = [h for h in REQUIRED_HEADERS if not request.headers.get(h)]
    if missing:
        raise HTTPException(
            status_code=403,
            detail=f"Missing required headers or Bearer token: {', '.join(missing)}",
        )


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    dependencies=[Depends(verify_authorization)],
)
async def proxy_fhir(request: Request, path: str):
    """Forward any FHIR request to the HAPI FHIR server."""
    target_url = f"{settings.hapi_base_url}/{path}"

    fwd_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in HOP_BY_HOP and k.lower() != "authorization"
    }

    body = await request.body()

    logger.info("FHIR proxy %s %s -> %s", request.method, path, target_url)

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.request(
            method=request.method,
            url=target_url,
            params=request.query_params,
            headers=fwd_headers,
            content=body,
        )

    resp_headers = {
        k: v for k, v in resp.headers.items()
        if k.lower() not in HOP_BY_HOP
    }

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=resp_headers,
    )
