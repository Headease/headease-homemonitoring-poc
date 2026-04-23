"""NVI registration via nuts-knooppunt — proxies through the knooppunt which handles pseudonymisation."""

import uuid

import httpx
from fastapi import APIRouter

from app.config import settings

router = APIRouter()

DATA_CATEGORIES_CS = "http://minvws.github.io/generiekefuncties-docs/CodeSystem/nl-gf-data-categories-cs"
BSN_SYSTEM = "http://fhir.nl/fhir/NamingSystem/bsn"
CUSTODIAN_EXT_URL = "http://minvws.github.io/generiekefuncties-docs/StructureDefinition/nl-gf-localization-custodian"

DEVICE_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, "headease-homemonitoring-poc"))

# The knooppunt runs as a sidecar/service in the same namespace
NK_INTERNAL_URL = f"http://{settings.nk_host}:8081"

DATA_CATEGORIES = [
    ("Patient", "Patient"),
    ("ObservationVitalSigns", "Observation (category: Vital Signs)"),
]


def _tenant_header() -> dict:
    return {"X-Tenant-ID": f"http://fhir.nl/fhir/NamingSystem/ura|{settings.ura_number}"}


def _build_list_resource(bsn: str, code: str, display: str) -> dict:
    """Build a FHIR List resource with plain BSN — knooppunt handles pseudonymisation."""
    return {
        "resourceType": "List",
        "extension": [
            {
                "url": CUSTODIAN_EXT_URL,
                "valueReference": {
                    "identifier": {
                        "system": "http://fhir.nl/fhir/NamingSystem/ura",
                        "value": settings.ura_number,
                    }
                },
            }
        ],
        "status": "current",
        "mode": "working",
        "code": {
            "coding": [
                {
                    "system": DATA_CATEGORIES_CS,
                    "code": code,
                    "display": display,
                }
            ]
        },
        "subject": {
            "identifier": {
                "system": BSN_SYSTEM,
                "value": bsn,
            }
        },
        "source": {
            "identifier": {
                "system": "urn:ietf:rfc:3986",
                "value": f"urn:uuid:{DEVICE_ID}",
            },
            "type": "Device",
        },
        "emptyReason": {
            "coding": [
                {
                    "code": "withheld",
                    "system": "http://terminology.hl7.org/CodeSystem/list-empty-reason",
                }
            ]
        },
    }


@router.post("/register-nvi-nk")
async def register_at_nvi_via_knooppunt(bsn: str = "004895708"):
    """Register localization records at the NVI via the nuts-knooppunt.

    The knooppunt handles pseudonymisation — we send plain BSNs.
    Treats 409 (already exists) as success.
    """
    headers = {
        "Content-Type": "application/fhir+json",
        **_tenant_header(),
    }

    async with httpx.AsyncClient(timeout=30) as client:
        results = []
        for code, display in DATA_CATEGORIES:
            list_resource = _build_list_resource(bsn, code, display)
            resp = await client.post(
                f"{NK_INTERNAL_URL}/nvi/List",
                json=list_resource,
                headers=headers,
            )
            status = resp.status_code
            # 409 = already registered, treat as success
            result = {"code": code, "status": status}
            if status == 409:
                result["note"] = "already registered"
            else:
                result["response"] = resp.json()
            results.append(result)

    return {
        "bsn": bsn,
        "via": "nuts-knooppunt",
        "registered": results,
    }


@router.get("/nvi-check-nk")
async def check_nvi_registration_via_knooppunt(bsn: str = "004895708"):
    """Check NVI registration via the nuts-knooppunt.

    The knooppunt handles pseudonymisation — we query with plain BSN.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{NK_INTERNAL_URL}/nvi/List",
            params={"subject:identifier": f"{BSN_SYSTEM}|{bsn}"},
            headers=_tenant_header(),
        )
        return {"bsn": bsn, "via": "nuts-knooppunt", "status": resp.status_code, "response": resp.json()}
