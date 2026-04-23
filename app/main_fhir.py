"""FHIR service — public-facing FHIR endpoints and OAuth token endpoint."""

import logging

from fastapi import FastAPI

logging.basicConfig(level=logging.INFO)
logging.getLogger("headease.http").setLevel(logging.INFO)

from app.fhir_routes import router as fhir_router
from app.token_endpoint import router as token_router

app = FastAPI(title="HeadEase FHIR Service", version="0.5.0")

app.include_router(fhir_router, prefix="/fhir")
app.include_router(token_router)


@app.get("/")
async def root():
    return {"status": "ok", "service": "HeadEase FHIR Data Holder"}
