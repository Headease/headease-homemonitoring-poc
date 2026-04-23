# nuts-knooppunt — Fixes for Proeftuin Compatibility

Compatibility issues found during the GF Proeftuin hackathon (April 2026), discovered by comparing the nuts-knooppunt pseudonymisation implementation against a working Python reference implementation and the PRS/NVI proeftuin services.

## Context

The proeftuin services (PRS, NVI, OAuth) are running at:
- PRS: `https://pseudoniemendienst.proeftuin.gf.irealisatie.nl`
- NVI: `https://nvi.proeftuin.gf.irealisatie.nl`
- OAuth: `https://oauth.proeftuin.gf.irealisatie.nl`

The reference Python implementation that works end-to-end is at:
https://github.com/Headease/headease-homemonitoring-poc

---

## Fix 1: JSON serialization must include spaces (blinding.go) — DONE

**File:** `component/pseudonymisation/blinding.go` (around line 19)

**Problem:** Go's `json.Marshal` produces compact JSON without spaces (`{"landCode":"NL",...}`), but the PRS reference implementation (Python) and the proeftuin PRS use JSON with spaces after `:` and `,` (`{"landCode": "NL", ...}`). Since this JSON string is the HKDF input, different serialization → different pseudonym → registrations can't be found.

**Fix applied:** Custom serialization that matches Python's `json.dumps` default (space after `:` and `,`).

**Verified:** HKDF pseudonyms now match between Python reference and knooppunt.

---

## Fix 2: OAuth client assertion field names (oauth2.go) — DONE

**File:** `component/authn/oauth2.go` (around line 144)

**Problem:** The form field names `client_credentials_type` and `client_credentials` are incorrect. The OAuth 2.0 JWT Bearer spec (RFC 7523) defines them as `client_assertion_type` and `client_assertion`.

**Fix applied:** Renamed to `client_assertion_type` and `client_assertion`.

**Verified:** OAuth token acquisition now succeeds against the proeftuin OAuth server.

---

## Fix 3: `encryptedPersonalId` encoding in PRS request (component.go) — DONE

**File:** `component/pseudonymisation/component.go` (around line 119-123)

**Problem:** The `EncryptedPersonalID` field was declared as `[]byte`, which Go's `json.Marshal` encodes as **base64 standard encoding** (alphabet `A-Za-z0-9+/`). The PRS expects **base64url encoding** (alphabet `A-Za-z0-9-_`).

**Fix applied:** Changed field to `string` with explicit `base64.RawURLEncoding.EncodeToString()`.

**Verified:** The PRS explicitly validates this field as base64url (see [models.py](https://github.com/minvws/gfmodules-pseudoniemendienst/blob/main/oprf/models.py)). Before the fix, sending base64 standard encoding caused `400 Bad Request: "Unable to evaluate blind"`.

---

## Observation: `blind_factor` encoding in NVI subject identifier (component.go)

**File:** `component/pseudonymisation/component.go` (around line 97-111)

**Status:** Not confirmed as an issue. No fix needed currently.

The `BlindFactor` field is declared as `[]byte`, which Go's `json.Marshal` encodes as base64 standard (alphabet `+/`). The Python reference uses base64url (alphabet `-_`). For ~50% of blind factors these produce different strings.

However, the NVI stores the `blind_factor` opaquely in `subject:identifier` — it does not decode or validate it ([NVI source](https://github.com/minvws/gfmodules-nationale-verwijsindex)). The `blind_factor` is only used by the data user when deblinding, so the encoding only needs to be consistent within a single implementation.

**Recommendation:** Only revisit if `Organization/$localize` or data user deblinding fails for knooppunt-registered records.

---

## Observation: outer envelope base64 encoding

**File:** `component/pseudonymisation/component.go` line 110

The knooppunt uses `base64.RawURLEncoding` (no padding) for the outer NVI identifier envelope. The Python reference uses `base64.urlsafe_b64encode` (with padding). The NVI accepts both. No fix needed.

---

## How to verify

The Python reference implementation logs HKDF inputs and pseudonym for comparison:

```
INFO:headease.pseudonymisation:HKDF info: ura:90000901|nationale-verwijsindex|v1
INFO:headease.pseudonymisation:HKDF pid:  {"landCode": "NL", "type": "BSN", "value": "004895708"}
INFO:headease.pseudonymisation:HKDF pseudonym: <base64url 32 bytes>
```

Cross-implementation test:

```bash
# Register via knooppunt
curl -X POST "http://localhost:8081/nvi/List" \
  -H "Content-Type: application/fhir+json" \
  -H "X-Tenant-ID: http://fhir.nl/fhir/NamingSystem/ura|90000315" \
  -d '{ ... List resource with BSN ... }'

# Check via Python reference (should find the knooppunt's record)
curl "https://admin.gf-cumuluz-poc.headease.nl/admin/nvi-check?bsn=004895708"

# And vice versa
curl -X POST "https://admin.gf-cumuluz-poc.headease.nl/admin/register-nvi?bsn=004895708"
curl "https://admin.gf-cumuluz-poc.headease.nl/admin/nvi-check-nk?bsn=004895708"
```
