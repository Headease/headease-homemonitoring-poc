"""Combined app — runs both FHIR and Admin services (for local development)."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query

logging.basicConfig(level=logging.INFO)
logging.getLogger("headease.http").setLevel(logging.INFO)

from app.fhir_routes import router as fhir_router
from app.nvi import router as nvi_router
from app.nvi_nk import router as nvi_nk_router
from app.oauth import get_nvi_token, get_prs_token, get_token
from app.registration import router as registration_router
from app.seeder import seed_hapi
from app.token_endpoint import router as token_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(seed_hapi())
    yield


app = FastAPI(title="HeadEase Home Monitoring PoC", version="0.10.0", lifespan=lifespan)

app.include_router(fhir_router, prefix="/fhir")
app.include_router(registration_router, prefix="/admin")
app.include_router(nvi_router, prefix="/admin")
app.include_router(nvi_nk_router, prefix="/admin")
app.include_router(token_router)


@app.get("/")
async def root():
    return {"status": "ok", "service": "HeadEase Home Monitoring Data Holder"}


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
