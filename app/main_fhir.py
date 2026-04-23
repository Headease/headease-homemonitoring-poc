"""FHIR service — public-facing FHIR proxy and OAuth token endpoint."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

logging.basicConfig(level=logging.INFO)
logging.getLogger("headease.http").setLevel(logging.INFO)

from app.fhir_routes import router as fhir_router
from app.seeder import seed_hapi
from app.token_endpoint import router as token_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Kick off HAPI seeding in background so startup isn't blocked
    asyncio.create_task(seed_hapi())
    yield


app = FastAPI(title="HeadEase FHIR Service", version="0.10.0", lifespan=lifespan)

app.include_router(fhir_router, prefix="/fhir")
app.include_router(token_router)


@app.get("/")
async def root():
    return {"status": "ok", "service": "HeadEase FHIR Data Holder"}
