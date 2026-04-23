"""LRZa registration — register Organization and Endpoints at the adressering service."""

import httpx
from fastapi import APIRouter

from app.config import settings
from app.http_client import create_client

router = APIRouter()

DATA_CATEGORIES_CS = "http://minvws.github.io/generiekefuncties-docs/CodeSystem/nl-gf-data-categories-cs"


def _build_organization() -> dict:
    return {
        "resourceType": "Organization",
        "identifier": [
            {
                "system": "http://fhir.nl/fhir/NamingSystem/ura",
                "value": settings.ura_number,
            }
        ],
        "name": settings.organization_name,
        "active": True,
    }


def _managing_org_ref(org_id: str) -> dict:
    """Build a managingOrganization with both reference and identifier."""
    return {
        "reference": f"Organization/{org_id}",
        "identifier": {
            "system": "http://fhir.nl/fhir/NamingSystem/ura",
            "value": settings.ura_number,
        },
    }


def _build_fhir_endpoint(org_id: str) -> dict:
    return {
        "resourceType": "Endpoint",
        "status": "active",
        "connectionType": {
            "system": "http://terminology.hl7.org/CodeSystem/endpoint-connection-type",
            "code": "hl7-fhir-rest",
        },
        "name": f"{settings.organization_name} FHIR Endpoint",
        "managingOrganization": _managing_org_ref(org_id),
        "payloadType": [
            {
                "coding": [
                    {
                        "system": DATA_CATEGORIES_CS,
                        "code": "Patient",
                    }
                ]
            }
        ],
        "address": settings.fhir_base_url,
    }


def _build_oauth_endpoint(org_id: str) -> dict:
    return {
        "resourceType": "Endpoint",
        "status": "active",
        "connectionType": {
            "system": "http://terminology.hl7.org/CodeSystem/endpoint-connection-type",
            "code": "oauth2",
        },
        "name": f"{settings.organization_name} OAuth2 Endpoint",
        "managingOrganization": _managing_org_ref(org_id),
        "payloadType": [
            {
                "coding": [
                    {
                        "system": DATA_CATEGORIES_CS,
                        "code": "Patient",
                    }
                ]
            }
        ],
        "address": f"{settings.fhir_base_url.rstrip('/fhir')}/oauth2/token",
    }


async def _upsert_resource(client: httpx.AsyncClient, resource: dict, search_params: str) -> dict:
    """Create or update a resource using conditional create (If-None-Exist) or update via search+PUT."""
    resource_type = resource["resourceType"]
    base_url = f"{settings.lrza_base_url}/{resource_type}"

    # First, search for existing resource
    resp = await client.get(f"{base_url}?{search_params}")
    resp.raise_for_status()
    bundle = resp.json()

    if bundle.get("total", 0) > 0:
        # Update existing resource
        existing = bundle["entry"][0]["resource"]
        existing_id = existing["id"]
        resource["id"] = existing_id
        resp = await client.put(f"{base_url}/{existing_id}", json=resource)
        resp.raise_for_status()
        return {"action": "updated", "id": existing_id, "resource": resp.json()}
    else:
        # Create new resource
        resp = await client.post(base_url, json=resource)
        resp.raise_for_status()
        return {"action": "created", "resource": resp.json()}


@router.post("/register")
async def register_at_lrza():
    """Register Organization and Endpoints at the LRZa adressering service.

    Idempotent: searches for existing resources by identifier/URA and updates them,
    or creates new ones if they don't exist.
    """
    results = {}
    ura_search = f"identifier=http://fhir.nl/fhir/NamingSystem/ura|{settings.ura_number}"

    async with create_client() as client:
        results["organization"] = await _upsert_resource(
            client, _build_organization(), ura_search
        )
        org_id = results["organization"].get("id") or results["organization"]["resource"]["id"]

        results["fhir_endpoint"] = await _upsert_resource(
            client, _build_fhir_endpoint(org_id),
            f"name={settings.organization_name} FHIR Endpoint",
        )
        results["oauth_endpoint"] = await _upsert_resource(
            client, _build_oauth_endpoint(org_id),
            f"name={settings.organization_name} OAuth2 Endpoint",
        )

        # Patch Organization.endpoint to reference both Endpoints
        fhir_ep_id = results["fhir_endpoint"].get("id") or results["fhir_endpoint"]["resource"]["id"]
        oauth_ep_id = results["oauth_endpoint"].get("id") or results["oauth_endpoint"]["resource"]["id"]

        patch = [
            {
                "op": "replace",
                "path": "/endpoint",
                "value": [
                    {"reference": f"Endpoint/{fhir_ep_id}"},
                    {"reference": f"Endpoint/{oauth_ep_id}"},
                ],
            }
        ]
        patch_resp = await client.patch(
            f"{settings.lrza_base_url}/Organization/{org_id}",
            json=patch,
            headers={"Content-Type": "application/json-patch+json"},
        )
        patch_resp.raise_for_status()
        results["organization_endpoints_patch"] = {"status": patch_resp.status_code}

    return {"status": "registered", "results": results}
