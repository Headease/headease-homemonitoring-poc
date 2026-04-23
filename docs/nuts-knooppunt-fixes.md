# nuts-knooppunt — Proposed Fixes for Proeftuin Compatibility

Instructions for fixing compatibility issues found during the GF Proeftuin hackathon (April 2026). These were discovered by comparing the nuts-knooppunt pseudonymisation implementation against a working Python reference implementation and the PRS/NVI proeftuin services.

## Context

The proeftuin services (PRS, NVI, OAuth) are running at:
- PRS: `https://pseudoniemendienst.proeftuin.gf.irealisatie.nl`
- NVI: `https://nvi.proeftuin.gf.irealisatie.nl`
- OAuth: `https://oauth.proeftuin.gf.irealisatie.nl`

The reference Python implementation that works end-to-end is at:
https://github.com/Headease/headease-homemonitoring-poc

---

## Fix 1: JSON serialization must include spaces (blinding.go)

**File:** `component/pseudonymisation/blinding.go` (around line 19)

**Problem:** Go's `json.Marshal` produces compact JSON without spaces (`{"landCode":"NL",...}`), but the PRS reference implementation (Python) and the proeftuin PRS use JSON with spaces after `:` and `,` (`{"landCode": "NL", ...}`). Since this JSON string is the HKDF input, different serialization → different pseudonym → registrations can't be found.

**Current code:**
```go
identifierJSON, err := json.Marshal(identifier)
```

**Fix:** Use a custom serialization that matches Python's `json.dumps` default (space after `:` and `,`):
```go
identifierJSON, err := json.Marshal(identifier)
if err != nil {
    return nil, err
}
// Match Python json.dumps default: spaces after separators
// This is required because the PRS reference implementation uses this format
identifierJSONSpaced := strings.ReplaceAll(string(identifierJSON), ",", ", ")
identifierJSONSpaced = strings.ReplaceAll(identifierJSONSpaced, ":", ": ")
```

Then use `[]byte(identifierJSONSpaced)` as the HKDF input.

**Verification:** For BSN `004895708`, the HKDF input should be exactly:
```
{"landCode": "NL", "type": "BSN", "value": "004895708"}
```

**Impact:** Without this fix, the knooppunt produces different pseudonyms than the reference implementation and the proeftuin PRS test endpoint, making registrations invisible to other participants.

---

## Fix 2: OAuth client assertion field names (oauth2.go)

**File:** `component/authn/oauth2.go` (around line 144)

**Problem:** The form field names `client_credentials_type` and `client_credentials` are incorrect. The OAuth 2.0 JWT Bearer spec (RFC 7523) defines them as `client_assertion_type` and `client_assertion`.

**Current code:**
```go
"client_credentials_type": {"urn:ietf:params:oauth:client-assertion-type:jwt-bearer"},
"client_credentials":      {string(jwtGrantTokenSigned)},
```

**Fix:**
```go
"client_assertion_type": {"urn:ietf:params:oauth:client-assertion-type:jwt-bearer"},
"client_assertion":      {string(jwtGrantTokenSigned)},
```

**Impact:** The proeftuin OAuth server may be lenient, but this is not spec-compliant and will fail against stricter implementations.

---

## Fix 2: `encryptedPersonalId` encoding in PRS request (component.go)

**File:** `component/pseudonymisation/component.go` (around line 119-123)

**Problem:** The `EncryptedPersonalID` field is declared as `[]byte`, which Go's `json.Marshal` encodes as **base64 standard encoding** (alphabet `A-Za-z0-9+/`). The PRS expects **base64url encoding** (alphabet `A-Za-z0-9-_`), matching the Python reference implementation.

**Current code:**
```go
type prsEvaluateRequest struct {
    RecipientOrganization string `json:"recipientOrganization"`
    RecipientScope        string `json:"recipientScope"`
    EncryptedPersonalID   []byte `json:"encryptedPersonalId"`
}
```

**Fix:** Change the field to `string` and encode explicitly with base64url:
```go
type prsEvaluateRequest struct {
    RecipientOrganization string `json:"recipientOrganization"`
    RecipientScope        string `json:"recipientScope"`
    EncryptedPersonalID   string `json:"encryptedPersonalId"`
}
```

And in `callPRSEvaluate`, encode the blinded input:
```go
requestBody := prsEvaluateRequest{
    RecipientOrganization: "ura:" + recipientURA,
    RecipientScope:        scope,
    EncryptedPersonalID:   base64.RawURLEncoding.EncodeToString(blindedInputData),
}
```

**Impact:** Different encoding may cause the PRS to evaluate differently, producing non-matching pseudonyms.

---

## Fix 3: `blind_factor` encoding in NVI subject identifier (component.go)

**File:** `component/pseudonymisation/component.go` (around line 97-111)

**Problem:** The `BlindFactor` field is declared as `[]byte`, which Go encodes as base64 standard. The NVI and reference implementations expect base64url encoding for the blind factor value.

**Current code:**
```go
type subjectIdentifier struct {
    BlindFactor     []byte `json:"blind_factor"`
    EvaluatedOutput string `json:"evaluated_output"`
}
```

**Fix:** Change to `string` and encode explicitly:
```go
type subjectIdentifier struct {
    BlindFactor     string `json:"blind_factor"`
    EvaluatedOutput string `json:"evaluated_output"`
}
```

And in `marshalSubjectIdentifier`:
```go
func marshalSubjectIdentifier(blindFactor []byte, evaluatedOutput string) (string, error) {
    data, err := json.Marshal(subjectIdentifier{
        BlindFactor:     base64.RawURLEncoding.EncodeToString(blindFactor),
        EvaluatedOutput: evaluatedOutput,
    })
    if err != nil {
        return "", fmt.Errorf("marshaling subject identifier: %w", err)
    }
    return base64.RawURLEncoding.EncodeToString(data), nil
}
```

**Impact:** The NVI needs the blind factor to deblind the pseudonym. Wrong encoding means the NVI can't resolve the patient identity, making registrations unfindable.

---

## Fix 4: Verify outer envelope uses base64url without padding

**File:** `component/pseudonymisation/component.go` line 110

**Current code** already uses `base64.RawURLEncoding` (no padding) — this is correct. Just confirm that the NVI and PRS expect this format (the Python reference uses `base64.urlsafe_b64encode` which includes padding, but the NVI seems to accept both).

---

## How to verify

After applying the fixes, the pseudonyms should be identical to those produced by the Python reference. You can verify by:

1. Computing the HKDF pseudonym for the same BSN in both implementations — they should match:
   - Input: `{"landCode": "NL", "type": "BSN", "value": "004895708"}` (with spaces after `:` and `,`)
   - Info: `ura:90000901|nationale-verwijsindex|v1`
   - The derived 32-byte pseudonym (base64url) should be identical

2. Registering a BSN via the knooppunt and querying the NVI directly (or vice versa) — both should find the same record

3. The reference implementation logs the HKDF inputs and pseudonym for easy comparison:
   ```
   INFO:headease.pseudonymisation:HKDF info: ura:90000901|nationale-verwijsindex|v1
   INFO:headease.pseudonymisation:HKDF pid:  {"landCode": "NL", "type": "BSN", "value": "004895708"}
   INFO:headease.pseudonymisation:HKDF pseudonym: <base64url 32 bytes>
   ```

## Test script

```bash
# Register via knooppunt
curl -X POST "http://localhost:8081/nvi/List" \
  -H "Content-Type: application/fhir+json" \
  -H "X-Tenant-ID: http://fhir.nl/fhir/NamingSystem/ura|90000315" \
  -d '{ ... List resource with BSN ... }'

# Check via Python reference (should find the record)
curl "https://admin.gf-cumuluz-poc.headease.nl/admin/nvi-check?bsn=004895708"
```
