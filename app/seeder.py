"""Seed sample Patient and Observation data into the HAPI FHIR server."""

import logging
import uuid
from datetime import datetime

import httpx

from app.config import settings

logger = logging.getLogger("headease.seeder")

SAMPLE_BSN = "004895708"
BSN_SYSTEM = "http://fhir.nl/fhir/NamingSystem/bsn"


def _make_patient(bsn: str) -> dict:
    return {
        "resourceType": "Patient",
        "identifier": [{"system": BSN_SYSTEM, "value": bsn}],
        "name": [{"family": "Demo", "given": ["Patient"]}],
    }


def _make_blood_pressure(patient_id: str, systolic: int = 120, diastolic: int = 80) -> dict:
    return {
        "resourceType": "Observation",
        "status": "final",
        "category": [{"coding": [{
            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
            "code": "vital-signs",
        }]}],
        "code": {"coding": [{
            "system": "http://loinc.org", "code": "85354-9", "display": "Blood pressure panel",
        }]},
        "subject": {"reference": f"Patient/{patient_id}"},
        "effectiveDateTime": datetime.now().isoformat(),
        "component": [
            {
                "code": {"coding": [{"system": "http://loinc.org", "code": "8480-6", "display": "Systolic blood pressure"}]},
                "valueQuantity": {"value": systolic, "unit": "mmHg", "system": "http://unitsofmeasure.org", "code": "mm[Hg]"},
            },
            {
                "code": {"coding": [{"system": "http://loinc.org", "code": "8462-4", "display": "Diastolic blood pressure"}]},
                "valueQuantity": {"value": diastolic, "unit": "mmHg", "system": "http://unitsofmeasure.org", "code": "mm[Hg]"},
            },
        ],
    }


def _make_body_weight(patient_id: str, weight_kg: float = 75.0) -> dict:
    return {
        "resourceType": "Observation",
        "status": "final",
        "category": [{"coding": [{
            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
            "code": "vital-signs",
        }]}],
        "code": {"coding": [{
            "system": "http://loinc.org", "code": "29463-7", "display": "Body weight",
        }]},
        "subject": {"reference": f"Patient/{patient_id}"},
        "effectiveDateTime": datetime.now().isoformat(),
        "valueQuantity": {"value": weight_kg, "unit": "kg", "system": "http://unitsofmeasure.org", "code": "kg"},
    }


async def seed_hapi():
    """Seed sample data into HAPI if the sample BSN isn't already there.

    Retries a few times to wait for HAPI startup.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        # Wait for HAPI to be ready
        max_attempts = 150  # 150 × 2s = 5 min
        for attempt in range(max_attempts):
            try:
                r = await client.get(f"{settings.hapi_base_url}/metadata")
                if r.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            if attempt % 10 == 0:
                logger.info("Waiting for HAPI (%d/%d)...", attempt + 1, max_attempts)
            import asyncio
            await asyncio.sleep(2)
        else:
            logger.error("HAPI not reachable at %s after %d attempts", settings.hapi_base_url, max_attempts)
            return False

        # Check if already seeded
        r = await client.get(
            f"{settings.hapi_base_url}/Patient",
            params={"identifier": f"{BSN_SYSTEM}|{SAMPLE_BSN}"},
        )
        if r.status_code == 200 and r.json().get("total", 0) > 0:
            logger.info("HAPI already has sample data for BSN %s", SAMPLE_BSN)
            return True

        # Create Patient
        r = await client.post(f"{settings.hapi_base_url}/Patient", json=_make_patient(SAMPLE_BSN))
        if r.status_code not in (200, 201):
            logger.error("Failed to create Patient: %d %s", r.status_code, r.text[:200])
            return False
        patient_id = r.json()["id"]
        logger.info("Created Patient/%s for BSN %s", patient_id, SAMPLE_BSN)

        # Create observations
        for obs in [
            _make_blood_pressure(patient_id, 130, 85),
            _make_blood_pressure(patient_id, 125, 82),
            _make_blood_pressure(patient_id, 118, 78),
            _make_body_weight(patient_id, 74.5),
            _make_body_weight(patient_id, 75.0),
            _make_body_weight(patient_id, 74.8),
        ]:
            r = await client.post(f"{settings.hapi_base_url}/Observation", json=obs)
            if r.status_code not in (200, 201):
                logger.warning("Failed to create Observation: %d %s", r.status_code, r.text[:200])

        logger.info("Seeded sample data for BSN %s", SAMPLE_BSN)
        return True
