# Home Monitoring Hackathon — Data Holder Script

Step-by-step script for HeadEase as **data holder** in the GF Proeftuin home monitoring use case.

## Prerequisites

- App running (locally or on GKE)
- Client certificates in `certificates/`

Set these environment variables:

```bash
export BASE_URL=https://data-source.gf-cumuluz-poc.headease.nl
export CERT=certificates/headease-certificates-proeftuin/headease-ldn-external-intermediate/headease-ldn-chain.crt
export KEY=certificates/headease_nvi_20260202_145627.key
export URA=90000315
```

## Step 1: Register at LRZa (adressering)

Register our Organization and Endpoints so data users can find us.

```bash
curl -X POST $BASE_URL/admin/register | python -m json.tool
```

This POSTs to `https://adressering.proeftuin.gf.irealisatie.nl/poc/FHIR/fhir/` using mTLS:

1. **Organization** — HeadEase with URA `90000315`
2. **FHIR Endpoint** — `$BASE_URL/fhir` with payloadType `Patient`
3. **OAuth Endpoint** — `$BASE_URL/oauth2/token`

**Expected result:** HTTP 200 with created resource IDs from the HAPI server.

**Verify in LRZa:**
```bash
curl --cert $CERT --key $KEY \
     "https://adressering.proeftuin.gf.irealisatie.nl/poc/FHIR/fhir/Organization?identifier=http://fhir.nl/fhir/NamingSystem/ura|$URA"
```

## Step 2: Register localization records at NVI

Make patient data findable by registering a pseudonymised localization record at the NVI.

### NVI API

Base URL: `https://nvi.proeftuin.gf.irealisatie.nl`

We register via `POST /v1-poc/fhir/List`. Auth: mTLS + Bearer token (OAuth scope `epd:write`).

OpenAPI spec: `https://nvi.proeftuin.gf.irealisatie.nl/openapi.json` (requires mTLS).

### Register

```bash
curl -X POST "$BASE_URL/admin/register-nvi?bsn=004895708" | python -m json.tool
```

This performs:

1. **Get OAuth tokens** — JWT client assertion → Bearer tokens for PRS and NVI
2. **Pseudonymise BSN** — HKDF + OPRF blind `{"landCode": "NL", "type": "BSN", "value": "004895708"}`, then call PRS `POST /oprf/eval` to get JWE
3. **Register at NVI** — `DELETE /v1-poc/fhir/List` (cleanup), then `POST /v1-poc/fhir/List` with pseudonymised subject, custodian URA, and data category

Idempotent: deletes existing records for our source before creating.

**Expected result:** HTTP 201 with created List resource.

### Verify registration

Check if we are findable for a given BSN:
```bash
curl "$BASE_URL/admin/nvi-check?bsn=004895708" | python -m json.tool
```

### Alternative: via nuts-knooppunt

The same operations are available via the nuts-knooppunt, which handles pseudonymisation transparently — you send plain BSNs:

**Register:**
```bash
curl -X POST "$BASE_URL/admin/register-nvi-nk?bsn=004895708" | python -m json.tool
```

**Verify:**
```bash
curl "$BASE_URL/admin/nvi-check-nk?bsn=004895708" | python -m json.tool
```

Both should produce identical NVI registrations. Use these to verify that the direct and knooppunt implementations match.

## Step 3: Serve FHIR data (passive — data users call us)

Once registered, data users will query our FHIR endpoints:

**Patient search:**
```bash
curl -X POST $BASE_URL/fhir/Patient/_search \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "x-ura-identifier: $URA" \
  -H "x-healthcareproviderroletype: doctor" \
  -H "x-dezi-identifier: user123" \
  -H "x-dezi-roletype: practitioner" \
  -d "identifier=http://fhir.nl/fhir/NamingSystem/bsn|004895708"
```

**Blood pressure (latest):**

You can use either the `Patient.id` from the search result, or the BSN identifier directly:

```bash
curl '$BASE_URL/fhir/Observation/$lastn?code=http://loinc.org|85354-9&patient=http://fhir.nl/fhir/NamingSystem/bsn|004895708' \
  -H "x-ura-identifier: $URA" \
  -H "x-healthcareproviderroletype: doctor" \
  -H "x-dezi-identifier: user123" \
  -H "x-dezi-roletype: practitioner"
```

**Body weight (latest):**
```bash
curl '$BASE_URL/fhir/Observation/$lastn?code=http://loinc.org|29463-7&patient=http://fhir.nl/fhir/NamingSystem/bsn|004895708' \
  -H "x-ura-identifier: $URA" \
  -H "x-healthcareproviderroletype: doctor" \
  -H "x-dezi-identifier: user123" \
  -H "x-dezi-roletype: practitioner"
```

> **Note:** Use single quotes around the URL to prevent `$lastn` from being interpreted as a shell variable. `$BASE_URL` won't expand inside single quotes — use double quotes for it or substitute manually.

## Open items

- [ ] Which `code` values to use for data categories (Patient vs specific observation codes?)
- [ ] Mitz consent verification (assumed for now)

## Status

| Step | Description      | Status                     |
|------|------------------|----------------------------|
| 1    | Register at LRZa | Done                       |
| 2    | Register at NVI  | Done                       |
| 3    | Serve FHIR data  | Ready (sample data seeded) |
