#!/usr/bin/env python3
"""Data User flow — discover and retrieve patient data across data holders.

Implements the 6-step data user script from:
https://github.com/minvws/generiekefuncties-docs/discussions/32

Usage (inside Docker — recommended, liboprf required):
    ./scripts/data-user.sh [BSN]

Or directly if liboprf is installed locally:
    source .venv/bin/activate
    python scripts/data-user.py [BSN]

Default BSN is 004895708.
"""

import asyncio
import base64
import json
import ssl
import sys
import time
import uuid
from pathlib import Path

import httpx
import jwt
from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding, load_pem_private_key

# Make app.* importable when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.oauth import _load_cert_der_b64, _cert_thumbprint_s256  # noqa: E402
from app.pseudonymisation import request_pseudonym  # noqa: E402


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.load_cert_chain(certfile=settings.ldn_chain_cert_path, keyfile=settings.client_key_path)
    return ctx


def _build_client_assertion_for(token_endpoint: str, scope: str, target_audience: str) -> str:
    """Build a JWT client assertion for any OAuth token endpoint."""
    now = int(time.time())
    private_key = load_pem_private_key(settings.client_key_path.read_bytes(), password=None)
    x5c = [
        _load_cert_der_b64(settings.uzi_cert_path),
        _load_cert_der_b64(settings.uzi_intermediate_cert_path),
    ]
    ldn_thumbprint = _cert_thumbprint_s256(settings.ldn_cert_path)
    payload = {
        "iss": settings.ura_number,
        "sub": settings.ura_number,
        "aud": token_endpoint,
        "scope": scope,
        "target_audience": target_audience,
        "iat": now,
        "exp": now + 300,
        "jti": str(uuid.uuid4()),
        "cnf": {"x5t#S256": ldn_thumbprint},
    }
    return jwt.encode(
        payload,
        private_key,
        algorithm="RS256",
        headers={"alg": "RS256", "typ": "JWT", "x5c": x5c},
    )


async def _get_proeftuin_token(scope: str, target_audience: str) -> str:
    """Get a Bearer token from the proeftuin OAuth server."""
    assertion = _build_client_assertion_for(
        f"{settings.oauth_base_url}/oauth/token", scope, target_audience
    )
    async with httpx.AsyncClient(verify=_ssl_context(), timeout=30) as client:
        resp = await client.post(
            f"{settings.oauth_base_url}/oauth/token",
            data={
                "grant_type": "client_credentials",
                "scope": scope,
                "target_audience": target_audience,
                "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                "client_assertion": assertion,
            },
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


# ============================================================================
# Step 1: Pseudonymise BSN via PRS
# ============================================================================
async def step1_pseudonymise(bsn: str) -> tuple[str, str]:
    print(f"\n[1/5] Pseudonymising BSN {bsn} via PRS...")
    nvi_identifier, blind_factor = await request_pseudonym(bsn)

    # Extract the JWE (just the evaluated_output) from the packaged NVI identifier
    padded = nvi_identifier + "=" * (-len(nvi_identifier) % 4)
    data = json.loads(base64.urlsafe_b64decode(padded))
    print(f"      NVI identifier: {nvi_identifier[:40]}...")
    print(f"      JWE pseudonym:  {data['evaluated_output'][:40]}...")
    return nvi_identifier, data["evaluated_output"]


# ============================================================================
# Step 2: Query NVI for data holders
# ============================================================================
async def step2_query_nvi(nvi_identifier: str) -> list[str]:
    print("\n[2/5] Querying NVI for data holders...")
    token = await _get_proeftuin_token("epd:write", settings.nvi_base_url)
    nvi_id_system = "http://minvws.github.io/generiekefuncties-docs/NamingSystem/nvi-identifier"

    async with httpx.AsyncClient(verify=_ssl_context(), timeout=30) as client:
        resp = await client.get(
            f"{settings.nvi_base_url}/v1-poc/fhir/List",
            params={
                "subject:identifier": f"{nvi_id_system}|{nvi_identifier}",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        bundle = resp.json()

    uras = set()
    for entry in bundle.get("entry", []):
        lst = entry.get("resource", {})
        for ext in lst.get("extension", []):
            if ext.get("url", "").endswith("nl-gf-localization-custodian"):
                ident = ext.get("valueReference", {}).get("identifier", {})
                if ident.get("value"):
                    uras.add(ident["value"])

    print(f"      Found {len(uras)} data holder(s): {sorted(uras)}")
    return sorted(uras)


# ============================================================================
# Step 3: Look up Endpoints in LRZa
# ============================================================================
async def step3_get_endpoints(ura: str) -> tuple[str | None, str | None]:
    print(f"\n[3/5] Looking up endpoints for URA {ura} in LRZa...")
    async with httpx.AsyncClient(verify=_ssl_context(), timeout=30) as client:
        # FHIR endpoint (payloadType=Patient)
        resp = await client.get(
            f"{settings.lrza_base_url}/Endpoint",
            params={
                "organization.identifier": f"http://fhir.nl/fhir/NamingSystem/ura|{ura}",
                "connection-type": "hl7-fhir-rest",
            },
        )
        resp.raise_for_status()
        fhir_bundle = resp.json()

        # OAuth endpoint
        resp = await client.get(
            f"{settings.lrza_base_url}/Endpoint",
            params={
                "organization.identifier": f"http://fhir.nl/fhir/NamingSystem/ura|{ura}",
                "connection-type": "oauth2",
            },
        )
        resp.raise_for_status()
        oauth_bundle = resp.json()

    fhir_addr = None
    for entry in fhir_bundle.get("entry", []):
        r = entry.get("resource", {})
        if r.get("address"):
            fhir_addr = r["address"]
            break

    oauth_addr = None
    for entry in oauth_bundle.get("entry", []):
        r = entry.get("resource", {})
        if r.get("address"):
            oauth_addr = r["address"]
            break

    print(f"      FHIR endpoint:  {fhir_addr}")
    print(f"      OAuth endpoint: {oauth_addr}")
    return fhir_addr, oauth_addr


# ============================================================================
# Step 4: Request access token from data holder
# ============================================================================
async def step4_get_access_token(oauth_endpoint: str, fhir_endpoint: str) -> str:
    print(f"\n[4/5] Requesting access token from {oauth_endpoint}...")
    assertion = _build_client_assertion_for(oauth_endpoint, "patient/*.rs", fhir_endpoint)

    headers = {
        "x-ura-identifier": settings.ura_number,
        "x-healthcareproviderroletype": "doctor",
        "x-dezi-identifier": "data-user-script",
        "x-dezi-roletype": "practitioner",
    }

    async with httpx.AsyncClient(verify=False, timeout=30) as client:
        resp = await client.post(
            oauth_endpoint,
            data={
                "grant_type": "client_credentials",
                "scope": "patient/*.rs",
                "target_audience": fhir_endpoint,
                "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                "client_assertion": assertion,
            },
            headers=headers,
        )
        resp.raise_for_status()
        token = resp.json()["access_token"]

    print(f"      Got access token: {token[:30]}...")
    return token


# ============================================================================
# Step 5: Retrieve patient data
# ============================================================================
async def step5_query_patient_data(fhir_endpoint: str, token: str, bsn: str) -> dict:
    print(f"\n[5/5] Retrieving data from {fhir_endpoint}...")
    headers = {
        "Authorization": f"Bearer {token}",
        "x-ura-identifier": settings.ura_number,
        "x-healthcareproviderroletype": "doctor",
        "x-dezi-identifier": "data-user-script",
        "x-dezi-roletype": "practitioner",
    }

    result = {}
    async with httpx.AsyncClient(verify=False, timeout=30) as client:
        # 5A: Patient search
        resp = await client.post(
            f"{fhir_endpoint}/Patient/_search",
            data={"identifier": f"http://fhir.nl/fhir/NamingSystem/bsn|{bsn}"},
            headers={**headers, "Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        patient_bundle = resp.json()
        if patient_bundle.get("total", 0) == 0:
            print("      No patient found")
            return result

        patient = patient_bundle["entry"][0]["resource"]
        patient_id = patient["id"]
        result["patient"] = patient
        print(f"      Patient/{patient_id}")

        def _filter_by_code(bundle: dict, code: str) -> list[dict]:
            """Return observations matching the given LOINC code, newest first."""
            out = []
            for entry in bundle.get("entry", []):
                obs = entry.get("resource", {})
                if any(c.get("code") == code for c in obs.get("code", {}).get("coding", [])):
                    out.append(obs)
            out.sort(key=lambda o: o.get("effectiveDateTime", ""), reverse=True)
            return out

        # 5B: Blood pressure
        resp = await client.get(
            f"{fhir_endpoint}/Observation/$lastn",
            params={"code": "http://loinc.org|85354-9", "patient": patient_id},
            headers=headers,
        )
        if resp.status_code == 200:
            bp = resp.json()
            result["blood_pressure"] = bp
            bp_obs = _filter_by_code(bp, "85354-9")
            print(f"      Blood pressure observations: {len(bp_obs)}")
            if bp_obs:
                components = bp_obs[0].get("component", [])
                sys_val = dia_val = None
                for c in components:
                    code = c["code"]["coding"][0]["code"]
                    val = c["valueQuantity"]["value"]
                    if code == "8480-6":
                        sys_val = val
                    elif code == "8462-4":
                        dia_val = val
                print(f"        Latest: {sys_val}/{dia_val} mmHg")

        # 5C: Body weight
        resp = await client.get(
            f"{fhir_endpoint}/Observation/$lastn",
            params={"code": "http://loinc.org|29463-7", "patient": patient_id},
            headers=headers,
        )
        if resp.status_code == 200:
            wt = resp.json()
            result["body_weight"] = wt
            wt_obs = _filter_by_code(wt, "29463-7")
            print(f"      Body weight observations:    {len(wt_obs)}")
            if wt_obs:
                val = wt_obs[0].get("valueQuantity", {}).get("value")
                print(f"        Latest: {val} kg")

    return result


# ============================================================================
# Main flow
# ============================================================================
async def main(bsn: str):
    print("=" * 72)
    print(f"Data User Flow for BSN {bsn}")
    print("=" * 72)

    nvi_identifier, _jwe = await step1_pseudonymise(bsn)
    uras = await step2_query_nvi(nvi_identifier)

    if not uras:
        print("\nNo data holders found for this BSN.")
        return

    all_results = {}
    for ura in uras:
        print("\n" + "-" * 72)
        print(f"Data holder URA: {ura}")
        print("-" * 72)
        try:
            fhir_ep, oauth_ep = await step3_get_endpoints(ura)
            if not fhir_ep or not oauth_ep:
                print(f"      Skipping {ura}: missing endpoint(s)")
                continue
            token = await step4_get_access_token(oauth_ep, fhir_ep)
            all_results[ura] = await step5_query_patient_data(fhir_ep, token, bsn)
        except httpx.HTTPStatusError as e:
            print(f"      Error: {e.response.status_code} {e.response.text[:200]}")
        except Exception as e:
            print(f"      Error: {type(e).__name__}: {e}")

    print("\n" + "=" * 72)
    print(f"Done. Retrieved data from {len(all_results)}/{len(uras)} data holder(s).")
    print("=" * 72)


if __name__ == "__main__":
    bsn = sys.argv[1] if len(sys.argv) > 1 else "004895708"
    asyncio.run(main(bsn))
