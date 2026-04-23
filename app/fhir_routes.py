"""FHIR API routes — Data Holder endpoints for Patient and Observation resources."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request

from app.token_store import get_token_context

router = APIRouter()

REQUIRED_HEADERS = [
    "x-ura-identifier",
    "x-healthcareproviderroletype",
    "x-dezi-identifier",
    "x-dezi-roletype",
]


async def verify_authorization(request: Request):
    """Verify authorization via Bearer token (Redis) or fallback to required headers."""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        context = await get_token_context(token)
        if context is None:
            raise HTTPException(status_code=401, detail="Invalid or expired Bearer token")
        # Token is valid — context contains the caller's identity
        request.state.token_context = context
        return

    # Fallback: check headers directly (for backward compatibility / testing)
    missing = [h for h in REQUIRED_HEADERS if not request.headers.get(h)]
    if missing:
        raise HTTPException(
            status_code=403,
            detail=f"Missing required headers or Bearer token: {', '.join(missing)}",
        )

# In-memory store of sample data (hackathon PoC)
PATIENTS: dict[str, dict] = {}
OBSERVATIONS: list[dict] = []


def _make_patient(bsn: str) -> dict:
    """Create a minimal FHIR Patient resource."""
    patient_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"bsn:{bsn}"))
    return {
        "resourceType": "Patient",
        "id": patient_id,
        "identifier": [
            {
                "system": "http://fhir.nl/fhir/NamingSystem/bsn",
                "value": bsn,
            }
        ],
        "name": [{"family": "Demo", "given": ["Patient"]}],
    }


def _make_blood_pressure(patient_id: str, systolic: int = 120, diastolic: int = 80) -> dict:
    """Create a FHIR Observation for blood pressure (LOINC 85354-9)."""
    return {
        "resourceType": "Observation",
        "id": str(uuid.uuid4()),
        "status": "final",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "vital-signs",
                    }
                ]
            }
        ],
        "code": {
            "coding": [{"system": "http://loinc.org", "code": "85354-9", "display": "Blood pressure panel"}]
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "effectiveDateTime": datetime.now().isoformat(),
        "component": [
            {
                "code": {
                    "coding": [{"system": "http://loinc.org", "code": "8480-6", "display": "Systolic blood pressure"}]
                },
                "valueQuantity": {"value": systolic, "unit": "mmHg", "system": "http://unitsofmeasure.org", "code": "mm[Hg]"},
            },
            {
                "code": {
                    "coding": [{"system": "http://loinc.org", "code": "8462-4", "display": "Diastolic blood pressure"}]
                },
                "valueQuantity": {"value": diastolic, "unit": "mmHg", "system": "http://unitsofmeasure.org", "code": "mm[Hg]"},
            },
        ],
    }


def _make_body_weight(patient_id: str, weight_kg: float = 75.0) -> dict:
    """Create a FHIR Observation for body weight (LOINC 29463-7)."""
    return {
        "resourceType": "Observation",
        "id": str(uuid.uuid4()),
        "status": "final",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "vital-signs",
                    }
                ]
            }
        ],
        "code": {
            "coding": [{"system": "http://loinc.org", "code": "29463-7", "display": "Body weight"}]
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "effectiveDateTime": datetime.now().isoformat(),
        "valueQuantity": {"value": weight_kg, "unit": "kg", "system": "http://unitsofmeasure.org", "code": "kg"},
    }


def seed_sample_data():
    """Seed the in-memory store with sample patient + observations."""
    bsn = "004895708"
    patient = _make_patient(bsn)
    PATIENTS[bsn] = patient
    pid = patient["id"]
    OBSERVATIONS.extend([
        _make_blood_pressure(pid, 130, 85),
        _make_blood_pressure(pid, 125, 82),
        _make_blood_pressure(pid, 118, 78),
        _make_body_weight(pid, 74.5),
        _make_body_weight(pid, 75.0),
        _make_body_weight(pid, 74.8),
    ])


# Seed on import
seed_sample_data()


@router.post("/Patient/_search", dependencies=[Depends(verify_authorization)])
async def search_patient(identifier: str = Form(...)):
    """Search Patient by identifier (BSN)."""
    # identifier format: http://fhir.nl/fhir/NamingSystem/bsn|004895708
    parts = identifier.split("|")
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="identifier must be system|value")
    bsn = parts[1]
    patient = PATIENTS.get(bsn)
    if not patient:
        return {"resourceType": "Bundle", "type": "searchset", "total": 0, "entry": []}
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": 1,
        "entry": [{"resource": patient, "fullUrl": f"Patient/{patient['id']}"}],
    }


@router.get("/Observation/$lastn", dependencies=[Depends(verify_authorization)])
async def observation_lastn(
    code: str = Query(..., description="system|code e.g. http://loinc.org|85354-9"),
    patient: str = Query(..., description="Patient resource ID or identifier (system|value)"),
    _count: int = Query(1, alias="_count"),
):
    """Return the most recent Observation(s) matching code and patient."""
    parts = code.split("|")
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="code must be system|code")
    system, code_value = parts

    # Resolve patient identifier (system|value) to patient ID
    patient_id = patient
    if "|" in patient:
        bsn = patient.split("|", 1)[1]
        p = PATIENTS.get(bsn)
        if not p:
            return {"resourceType": "Bundle", "type": "searchset", "total": 0, "entry": []}
        patient_id = p["id"]

    matching = [
        obs
        for obs in OBSERVATIONS
        if obs["subject"]["reference"] == f"Patient/{patient_id}"
        and any(c["system"] == system and c["code"] == code_value for c in obs["code"]["coding"])
    ]

    # Sort by effectiveDateTime descending, take _count
    matching.sort(key=lambda o: o["effectiveDateTime"], reverse=True)
    matching = matching[:_count]

    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(matching),
        "entry": [{"resource": obs, "fullUrl": f"Observation/{obs['id']}"} for obs in matching],
    }
