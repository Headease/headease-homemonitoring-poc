"""NVI registration — register localization records at the nationale verwijsindex."""

import uuid

from fastapi import APIRouter

from app.config import settings
from app.http_client import create_client
from app.oauth import get_nvi_token
from app.pseudonymisation import request_pseudonym

router = APIRouter()

DATA_CATEGORIES_CS = "http://minvws.github.io/generiekefuncties-docs/CodeSystem/nl-gf-data-categories-cs"
NVI_IDENTIFIER_SYSTEM = "http://minvws.github.io/generiekefuncties-docs/NamingSystem/nvi-identifier"
CUSTODIAN_EXT_URL = "http://minvws.github.io/generiekefuncties-docs/StructureDefinition/nl-gf-localization-custodian"

# Stable device ID for this software installation
DEVICE_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, "headease-homemonitoring-poc"))


def _build_list_resource(nvi_identifier: str) -> dict:
    """Build a FHIR List resource for NVI localization."""
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
                    "code": "Patient",
                    "display": "Patient",
                }
            ]
        },
        "subject": {
            "identifier": {
                "system": NVI_IDENTIFIER_SYSTEM,
                "value": nvi_identifier,
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


@router.post("/register-nvi")
async def register_at_nvi(bsn: str = "004895708"):
    """Register a localization record at the NVI via the FHIR List API.

    Idempotent: deletes existing List resources for our source device before creating.
    """
    nvi_identifier, _ = await request_pseudonym(bsn)
    token = await get_nvi_token()
    headers = {
        "Content-Type": "application/fhir+json",
        "Authorization": f"Bearer {token}",
    }

    async with create_client() as client:
        # Delete existing registrations for our source device
        delete_resp = await client.delete(
            f"{settings.nvi_base_url}/v1-poc/fhir/List",
            params={"source:identifier": f"urn:ietf:rfc:3986|urn:uuid:{DEVICE_ID}"},
            headers={"Authorization": f"Bearer {token}"},
        )

        # Create new List resource
        list_resource = _build_list_resource(nvi_identifier)
        resp = await client.post(
            f"{settings.nvi_base_url}/v1-poc/fhir/List",
            json=list_resource,
            headers=headers,
        )
        result = resp.json()

    return {
        "status": resp.status_code,
        "bsn": bsn,
        "previous_deleted": delete_resp.status_code,
        "response": result,
    }


@router.get("/nvi-check")
async def check_nvi_registration(bsn: str = "004895708"):
    """Pseudonymise a BSN and query the NVI to check if we are registered as data holder.

    Uses GET /v1-poc/fhir/List with subject:identifier.
    """
    nvi_identifier, _ = await request_pseudonym(bsn)
    token = await get_nvi_token()

    async with create_client() as client:
        resp = await client.get(
            f"{settings.nvi_base_url}/v1-poc/fhir/List",
            params={
                "subject:identifier": f"https://nvi.proeftuin.gf.irealisatie.nl/fhir/NamingSystem/nvi-pseudonym|{nvi_identifier}",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        return {"bsn": bsn, "status": resp.status_code, "response": resp.json()}
