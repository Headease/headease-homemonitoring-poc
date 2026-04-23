# Home Monitoring Hackathon — Data User Guide

Instruction document for the **data user** role in the GF Proeftuin home monitoring use case. This guide covers locating data holders, obtaining pseudonyms, and querying patient data (BloodPressure, BodyWeight).

## Proeftuin Services

| Service | Base URL | Swagger/Docs |
|---------|----------|--------------|
| OAuth | `https://oauth.proeftuin.gf.irealisatie.nl` | `/docs` |
| NVI | `https://nvi.proeftuin.gf.irealisatie.nl` | `/docs` |
| PRS | `https://pseudoniemendienst.proeftuin.gf.irealisatie.nl` | `/docs` |
| LRZa (HAPI FHIR) | `https://adressering.proeftuin.gf.irealisatie.nl/poc/FHIR/fhir` | `/swagger-ui/` |

All services require **mTLS** (mutual TLS) using the mock LDN certificate chain.

## Prerequisites

- Mock UZI certificate + intermediate (for signing JWTs)
- Mock LDN certificate chain (for mTLS connections)
- Private key matching both certificates
- Your organization's URA number

## Step 0: Obtain OAuth Tokens

All API calls to NVI and PRS require a Bearer token obtained from the OAuth service. The proeftuin uses OAuth 2.0 with JWT client assertions (RFC 7523).

### Build a JWT Client Assertion

**Header:**
```json
{
  "alg": "RS256",
  "typ": "JWT",
  "x5c": ["<base64 DER-encoded UZI cert>", "<base64 DER-encoded UZI intermediate cert>"]
}
```

> **Gotcha:** The intermediate `.cer` files are DER-encoded, not PEM. You may need to handle both formats when loading certificates.

**Payload:**
```json
{
  "iss": "<your-ura-number>",
  "sub": "<your-ura-number>",
  "aud": "https://oauth.proeftuin.gf.irealisatie.nl/oauth/token",
  "scope": "<scope>",
  "target_audience": "<target-service-url>",
  "iat": 1745312000,
  "exp": 1745312300,
  "jti": "<unique-uuid>",
  "cnf": {
    "x5t#S256": "<SHA-256 thumbprint of your LDN certificate>"
  }
}
```

Sign the JWT with your **UZI private key** (RS256).

### Request the Token

```bash
curl -X POST https://oauth.proeftuin.gf.irealisatie.nl/oauth/token \
  --cert ldn-chain.crt --key private.key \
  -d "grant_type=client_credentials" \
  -d "scope=prs:read" \
  -d "target_audience=https://pseudoniemendienst.proeftuin.gf.irealisatie.nl" \
  -d "client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer" \
  -d "client_assertion=<signed-jwt>"
```

**Scopes:**
- `prs:read` — for PRS calls (pseudonymisation)
- `epd:write` — for NVI calls (localization queries)

The `target_audience` must match the service you intend to call.

## Step 1: Pseudonymise the Patient BSN

Before querying the NVI, you need a pseudonymised BSN. The pseudonymisation uses OPRF (Oblivious Pseudorandom Function).

### 1a. Client-side Blinding

```python
import base64, json
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
import pysodium

personal_identifier = {"landCode": "NL", "type": "BSN", "value": "004895708"}

# The recipient is the NVI (URA 90000901), NOT your own organization
recipient_organization = "ura:90000901"
recipient_scope = "nationale-verwijsindex"

info = f"{recipient_organization}|{recipient_scope}|v1".encode("utf-8")
pid = json.dumps(personal_identifier).encode("utf-8")

pseudonym = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=info).derive(pid)

# OPRF blind using ristretto255
point = pysodium.crypto_core_ristretto255_from_hash(
    pysodium.crypto_generichash(pseudonym, outlen=64)
)
blind_factor = pysodium.crypto_core_ristretto255_scalar_random()
blinded_point = pysodium.crypto_scalarmult_ristretto255(blind_factor, point)

blind_factor_b64 = base64.urlsafe_b64encode(blind_factor).decode()
blinded_input_b64 = base64.urlsafe_b64encode(blinded_point).decode()
```

> **Critical:** The `recipientOrganization` must be the NVI's URA (`90000901`), not your own. The PRS encrypts the result for the recipient's public key. The scope at the PRS for the NVI is `nationale-verwijsindex`.

> **Dependency:** `pysodium` requires `libsodium`. The `pyoprf` package wraps this but needs `liboprf` (a native C library) which may not be available. Using `pysodium` directly with ristretto255 is a working alternative.

### 1b. Call PRS to Evaluate

```bash
curl -X POST https://pseudoniemendienst.proeftuin.gf.irealisatie.nl/oprf/eval \
  --cert ldn-chain.crt --key private.key \
  -H "Authorization: Bearer <prs-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "encryptedPersonalId": "<blinded_input_b64>",
    "recipientOrganization": "ura:90000901",
    "recipientScope": "nationale-verwijsindex"
  }'
```

> **Gotcha:** The PRS API field names differ from the spec documentation:
> - Endpoint is `/oprf/eval` (not `/evaluate`)
> - Field is `encryptedPersonalId` (not `blinded_input`)
> - Field is `recipientOrganization` (not `recipient_organization`)
> - Field is `recipientScope` (not `recipient_scope`)
> - Response field is `jwe` (not `evaluated_output`)

**Response:**
```json
{
  "jwe": "eyJraWQiOi..."
}
```

### 1c. Package the NVI Identifier

The NVI identifier is a base64url-encoded JSON object containing the JWE and blind factor:

```python
import base64, json

nvi_identifier = base64.urlsafe_b64encode(json.dumps({
    "evaluated_output": jwe,        # the JWE from PRS response
    "blind_factor": blind_factor_b64  # your client-side blind factor
}).encode()).decode()
```

### 1d. Test Endpoint (Shortcut)

The PRS provides a test endpoint that does the blinding server-side — useful for debugging:

```bash
curl -X POST https://pseudoniemendienst.proeftuin.gf.irealisatie.nl/test/oprf/client \
  --cert ldn-chain.crt --key private.key \
  -H "Authorization: Bearer <prs-token>" \
  -H "Content-Type: application/json" \
  -d '{"personalId": {"landCode": "NL", "type": "bsn", "value": "004895708"}}'
```

This returns `{"blinded_input": "...", "blind_factor": "..."}` which you can then send to `/oprf/eval`.

## Step 2: Locate Data Holders via NVI

Query the NVI to find which organizations hold data for a pseudonymised patient.

### Option A: Query via Organization/$localize

```bash
curl -X POST https://nvi.proeftuin.gf.irealisatie.nl/Organization/\$localize \
  --cert ldn-chain.crt --key private.key \
  -H "Authorization: Bearer <nvi-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "resourceType": "Parameters",
    "parameter": [
      {"name": "pseudonym", "valueString": "<jwe-from-prs>"},
      {"name": "oprfKey", "valueString": "<blind-factor-b64>"}
    ]
  }'
```

**Response:** A Bundle of Organization resources (with URA identifiers) that hold data for this patient.

You can optionally add a `careContext` parameter to filter by data category, using the `nl-gf-data-categories-cs` CodeSystem:

```json
{"name": "careContext", "valueCoding": {
  "system": "http://minvws.github.io/generiekefuncties-docs/CodeSystem/nl-gf-data-categories-cs",
  "code": "ObservationVitalSigns"
}}
```

Relevant codes for home monitoring: `Patient`, `ObservationVitalSigns`. See the full [ValueSet](https://minvws.github.io/generiekefuncties-docs/ValueSet-nl-gf-zorgcontext-vs.html) for all 28 codes.

### Option B: Query via List resources

Search by pseudonymised BSN and data category code (`Patient` or `ObservationVitalSigns`):

```bash
curl "https://nvi.proeftuin.gf.irealisatie.nl/v1-poc/fhir/List?subject:identifier=https://nvi.proeftuin.gf.irealisatie.nl/fhir/NamingSystem/nvi-pseudonym|<nvi-identifier>&code=http://minvws.github.io/generiekefuncties-docs/CodeSystem/nl-gf-data-categories-cs|Patient" \
  --cert ldn-chain.crt --key private.key \
  -H "Authorization: Bearer <nvi-token>"
```

HeadEase registers two data categories per patient:
- `Patient` — patient demographics
- `ObservationVitalSigns` — blood pressure, body weight

## Step 3: Obtain Data Holder Addresses from LRZa

Once you know which organizations hold data (from the NVI), look up their FHIR endpoints in the LRZa.

```bash
curl "https://adressering.proeftuin.gf.irealisatie.nl/poc/FHIR/fhir/Endpoint?managingOrganization.identifier=http://fhir.nl/fhir/NamingSystem/ura|90000315&connection-type=hl7-fhir-rest" \
  --cert ldn-chain.crt --key private.key
```

This returns the FHIR base URL of the data holder (e.g., `https://data-source.gf-cumuluz-poc.headease.nl/fhir`).

Also retrieve the OAuth endpoint for the data holder:
```bash
curl "https://adressering.proeftuin.gf.irealisatie.nl/poc/FHIR/fhir/Endpoint?managingOrganization.identifier=http://fhir.nl/fhir/NamingSystem/ura|90000315&connection-type=oauth2" \
  --cert ldn-chain.crt --key private.key
```

## Step 4: Request Data from the Data Holder

### 4a. Request an Access Token

Request an access token from the data holder's OAuth endpoint. Include the required headers:

- `x-ura-identifier` — your organization's URA number
- `x-healthcareproviderroletype` — your role type
- `x-dezi-identifier` — the user's identifier
- `x-dezi-roletype` — the user's role type

Scope: `patient/*.rs`

> **Note:** In the current PoC, the data holder (HeadEase) does not implement its own OAuth server. The authorization headers are validated directly on the FHIR endpoints.

### 4b. Search for the Patient

```bash
curl -X POST https://data-source.gf-cumuluz-poc.headease.nl/fhir/Patient/_search \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "x-ura-identifier: <your-ura>" \
  -H "x-healthcareproviderroletype: doctor" \
  -H "x-dezi-identifier: <user-id>" \
  -H "x-dezi-roletype: practitioner" \
  -d "identifier=http://fhir.nl/fhir/NamingSystem/bsn|004895708"
```

**Response:** A FHIR Bundle with the Patient resource. You can use either the `Patient.id` or the BSN identifier for subsequent Observation queries.

### 4c. Query Blood Pressure

```bash
curl 'https://data-source.gf-cumuluz-poc.headease.nl/fhir/Observation/$lastn?code=http://loinc.org|85354-9&patient=http://fhir.nl/fhir/NamingSystem/bsn|004895708' \
  -H "x-ura-identifier: <your-ura>" \
  -H "x-healthcareproviderroletype: doctor" \
  -H "x-dezi-identifier: <user-id>" \
  -H "x-dezi-roletype: practitioner"
```

LOINC `85354-9` = Blood pressure panel. The Observation contains components:
- `8480-6` — Systolic blood pressure (mmHg)
- `8462-4` — Diastolic blood pressure (mmHg)

### 4d. Query Body Weight

```bash
curl 'https://data-source.gf-cumuluz-poc.headease.nl/fhir/Observation/$lastn?code=http://loinc.org|29463-7&patient=http://fhir.nl/fhir/NamingSystem/bsn|004895708' \
  -H "x-ura-identifier: <your-ura>" \
  -H "x-healthcareproviderroletype: doctor" \
  -H "x-dezi-identifier: <user-id>" \
  -H "x-dezi-roletype: practitioner"
```

LOINC `29463-7` = Body weight (kg).

> **Note:** Use single quotes around the URL to prevent `$lastn` from being interpreted as a shell variable. The `patient` parameter accepts both a Patient resource ID and a BSN identifier (`system|value`).

## Gotchas and Lessons Learned

### Certificates
- You receive **two certificate chains**: UZI (for JWT signing) and LDN (for mTLS)
- **UZI cert** contains your URA number, used to sign JWT client assertions
- **LDN cert** is used for mTLS connections to all proeftuin services
- The intermediate `.cer` files are **DER-encoded**, not PEM — your code must handle both formats
- The LDN cert SHA-256 thumbprint goes in the JWT `cnf.x5t#S256` field

### OAuth
- Token endpoint: `POST https://oauth.proeftuin.gf.irealisatie.nl/oauth/token`
- Well-known config: `https://oauth.proeftuin.gf.irealisatie.nl/.well-known/oauth-authorization-server`
- The `target_audience` in both the JWT payload and the token request must match the service URL you intend to call
- mTLS (LDN cert) is required even for the OAuth token endpoint

### PRS (Pseudonymisation)
- The `recipientOrganization` is the **NVI** (URA `90000901`), not your own organization — the PRS encrypts the output for the recipient
- The `recipientScope` for the NVI is `nationale-verwijsindex`
- API field names use camelCase (`encryptedPersonalId`, `recipientOrganization`, `recipientScope`), not snake_case
- The response field is `jwe`, not `evaluated_output`
- The `pyoprf` Python package requires native `liboprf` which may not be available — use `pysodium` with ristretto255 directly as an alternative
- PRS OpenAPI spec: `https://pseudoniemendienst.proeftuin.gf.irealisatie.nl/openapi.json` (requires mTLS)
- The `/test/oprf/client` endpoint is useful for debugging — it does the blinding server-side

### NVI
- Registration via FHIR List API (`POST /v1-poc/fhir/List`)
- Querying via `GET /v1-poc/fhir/List` with `subject:identifier` using system `https://nvi.proeftuin.gf.irealisatie.nl/fhir/NamingSystem/nvi-pseudonym`
- The NVI's own URA is `90000901`
- The NVI identifier in `subject.identifier.value` is a base64url-encoded JSON containing `evaluated_output` (the JWE) and `blind_factor`
- HeadEase publishes two data categories: `Patient` and `ObservationVitalSigns`
- NVI OpenAPI spec: `https://nvi.proeftuin.gf.irealisatie.nl/openapi.json` (requires mTLS)

### LRZa
- Base URL: `https://adressering.proeftuin.gf.irealisatie.nl/poc/FHIR/fhir` (note the double `/FHIR/fhir`)
- This is a standard HAPI FHIR server — use normal FHIR search operations
- mTLS required, but no Bearer token needed

### Data Holder FHIR Endpoints
- Required authorization headers: `x-ura-identifier`, `x-healthcareproviderroletype`, `x-dezi-identifier`, `x-dezi-roletype`
- Missing headers return HTTP 403
- Patient search uses `POST /_search` with form-encoded `identifier` parameter
- Observation `$lastn` accepts `patient` as either a Patient resource ID or a BSN identifier (`http://fhir.nl/fhir/NamingSystem/bsn|004895708`)
- Use **single quotes** around URLs containing `$lastn` in shell to avoid variable interpolation
- Mitz consent is assumed (not enforced in the PoC)

## Test BSN Numbers

Use BSN numbers from the RvIG Omnummertabel. Do **not** use real person data. The proeftuin environment is closed one month after the hackathon and all data is deleted.

## Reference

- Implementation Guide: https://minvws.github.io/generiekefuncties-docs
- Input Script: https://github.com/minvws/generiekefuncties-docs/discussions/32
- Hackathon Info: https://github.com/minvws/generiekefuncties-docs/discussions/34
- Pseudonymisation: https://minvws.github.io/generiekefuncties-docs/pseudonymisation.html
- Localization: https://minvws.github.io/generiekefuncties-docs/localization.html
