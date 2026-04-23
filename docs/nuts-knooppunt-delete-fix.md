# nuts-knooppunt — Fix DELETE query parameter encoding

## Problem

`DELETE /nvi/List?source:identifier=...` fails with 400 at the NVI because query parameters are encoded into the URL path instead of being passed as query parameters.

The knooppunt sends:
```
DELETE https://nvi.proeftuin.gf.irealisatie.nl/v1-poc/fhir/List%3Fsource:identifier=urn:ietf:rfc:3986%7Curn:uuid:...
```

But should send:
```
DELETE https://nvi.proeftuin.gf.irealisatie.nl/v1-poc/fhir/List?source:identifier=urn:ietf:rfc:3986|urn:uuid:...
```

The `?` is being percent-encoded as `%3F` because it's passed as part of the path string.

## Root cause

**File:** `component/nvi/component.go`, line 308

```go
err = fhirClient.DeleteWithContext(httpRequest.Context(), "List?"+deleteParams.Encode())
```

`DeleteWithContext` calls `AtPath(path)` which uses `client.Path(path)` → `url.JoinPath(path)`. This treats the entire string `"List?source%3Aidentifier=..."` as a path segment, encoding the `?` as `%3F`.

## How the fhirclient works

From `go-fhir-client` (`client.go`):

```go
// AtPath sets the path on the request URL
func AtPath(path string) PreRequestOption {
    return func(client Client, r *http.Request) {
        query := r.URL.Query().Encode()
        r.URL = client.Path(path)       // JoinPath — encodes ? as %3F
        r.URL.RawQuery = query
    }
}

// QueryParam adds a query parameter to the request
func QueryParam(key, value string) PreRequestOption {
    return func(_ Client, r *http.Request) {
        q := r.URL.Query()
        q.Add(key, value)
        r.URL.RawQuery = q.Encode()
    }
}
```

## Fix

**File:** `component/nvi/component.go`, around line 308

Replace:
```go
err = fhirClient.DeleteWithContext(httpRequest.Context(), "List?"+deleteParams.Encode())
```

With:
```go
// Build query param options from deleteParams
var opts []fhirclient.Option
for key, values := range deleteParams {
    for _, value := range values {
        opts = append(opts, fhirclient.QueryParam(key, value))
    }
}
err = fhirClient.DeleteWithContext(httpRequest.Context(), "List", opts...)
```

This passes `"List"` as the path (no query string) and uses `QueryParam` options to add each parameter properly. The fhirclient will set them on `r.URL.RawQuery` instead of encoding them into the path.

## Tests to update

**File:** `component/nvi/component_test.go`

The test expectations will need to change. The stub `fhirClient.Deletions` list will now contain just `"List"` instead of `"List?subject%3Aidentifier=..."`. The query parameters should be verified separately, or the test stub needs to capture them.

## Verification

```bash
# From the admin service
curl -X POST "http://localhost:8001/admin/register-nvi-nk?bsn=004895708"
```

The knooppunt logs should show:
```
DELETE https://nvi.proeftuin.gf.irealisatie.nl/v1-poc/fhir/List?source:identifier=...
```

Not:
```
DELETE https://nvi.proeftuin.gf.irealisatie.nl/v1-poc/fhir/List%3Fsource:identifier=...
```
