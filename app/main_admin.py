"""Admin service — registration, NVI management, and proeftuin token helper."""

import logging

from fastapi import FastAPI, Query

logging.basicConfig(level=logging.INFO)
logging.getLogger("headease.http").setLevel(logging.INFO)

from app.nvi import router as nvi_router
from app.nvi_nk import router as nvi_nk_router
from app.oauth import get_nvi_token, get_prs_token, get_token
from app.registration import router as registration_router

app = FastAPI(title="HeadEase Admin Service", version="0.7.0")

app.include_router(registration_router, prefix="/admin")
app.include_router(nvi_router, prefix="/admin")
app.include_router(nvi_nk_router, prefix="/admin")


@app.get("/")
async def root():
    return {"status": "ok", "service": "HeadEase Admin"}


@app.get("/admin/token")
async def get_oauth_token(
    service: str = Query("nvi", description="Service to get token for: nvi, prs, or custom"),
    scope: str = Query(None, description="Custom scope (only with service=custom)"),
    target_audience: str = Query(None, description="Custom target audience (only with service=custom)"),
):
    """Get an OAuth Bearer token for a proeftuin service."""
    if service == "nvi":
        token = await get_nvi_token()
    elif service == "prs":
        token = await get_prs_token()
    elif service == "custom" and scope and target_audience:
        token = await get_token(scope, target_audience)
    else:
        return {"error": "Use service=nvi, service=prs, or service=custom with scope and target_audience"}
    return {"access_token": token, "service": service}
