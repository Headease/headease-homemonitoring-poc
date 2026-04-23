# CLAUDE.md

## Project Overview

HeadEase Home Monitoring PoC — a FastAPI app acting as a **data holder** in the GF Proeftuin home monitoring use case. Exposes FHIR Patient and Observation resources, registers at the LRZa adressering service, pseudonymises BSNs via the PRS, and registers localization records at the NVI.

## Tech Stack

- Python 3.12+, FastAPI, Uvicorn, httpx, cryptography, pydantic-settings, pysodium, PyJWT
- No database — in-memory data store (hackathon PoC)

## Project Structure

```
app/
├── main.py              # FastAPI app, includes routers + /admin/token endpoint
├── config.py            # Settings via pydantic-settings (env prefix: HEADEASE_)
├── fhir_routes.py       # FHIR endpoints: Patient/_search, Observation/$lastn
├── registration.py      # LRZa registration with mTLS client cert
├── pseudonymisation.py  # PRS client: HKDF + OPRF blinding via pysodium ristretto255
├── nvi.py               # NVI registration: List resources with pseudonymised BSN
└── oauth.py             # OAuth 2.0 client assertion flow (JWT signed with UZI cert)
docs/
├── SCRIPT.md            # Data holder step-by-step script
└── DATA-USER-GUIDE.md   # Data user instruction guide
```

## Running

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

## Key Commands

- Install: `pip install -e ".[dev]"`
- Lint: `ruff check app/`
- Format: `ruff format app/`
- Test: `pytest`

## Conventions

- FHIR resources are plain dicts, not Pydantic models (keep it simple for the PoC)
- **LDN cert** is used for mTLS connections to all proeftuin services
- **UZI cert** is used for signing JWT client assertions (contains URA number)
- Config values come from environment variables with `HEADEASE_` prefix or `.env` file
- Do not commit certificates, `.p12`, or `.key` files
- Intermediate `.cer` files are DER-encoded, not PEM — code handles both formats

## Certificate Roles

- `headease-uzi-chain.crt` / `headease-uzi.crt` — UZI cert for JWT signing
- `headease-ldn-chain.crt` / `headease-ldn.crt` — LDN cert for mTLS
- `gfmodules-test-uzi-external-intermediate.cer` — UZI intermediate (DER format)
- `headease_nvi_20260202_145627.key` — private key (shared by both cert chains)

## External Services

- **OAuth**: `https://oauth.proeftuin.gf.irealisatie.nl` — token endpoint at `/oauth/token`
- **LRZa**: `https://adressering.proeftuin.gf.irealisatie.nl/poc/FHIR/fhir` — HAPI FHIR server (note double `/FHIR/fhir`)
- **NVI**: `https://nvi.proeftuin.gf.irealisatie.nl` — nationale verwijsindex (URA `90000901`)
- **PRS**: `https://pseudoniemendienst.proeftuin.gf.irealisatie.nl` — pseudonymisation service
- **Public URL**: `https://data-source.gf-cumuluz-poc.headease.nl` — GKE deployment

## Key Implementation Details

- PRS `/oprf/eval` uses camelCase fields: `encryptedPersonalId`, `recipientOrganization`, `recipientScope`
- PRS response field is `jwe` (not `evaluated_output`)
- The `recipientOrganization` for PRS calls is the NVI (`ura:90000901`), not our own URA
- The `recipientScope` is `nationale-verwijsindex`
- OAuth tokens need `target_audience` matching the service URL and `cnf.x5t#S256` with LDN cert thumbprint

## Versioning & Release

The version is defined in `pyproject.toml` and used as the Docker image tag. When releasing a new version, update these files:

1. `CHANGELOG.md` — add a new section with the changes
2. `pyproject.toml` — bump the `version` field
3. `terraform/variables.tf` — update the `image_tag` default to match

The GitHub Actions workflow reads the version from `pyproject.toml` and tags the Docker image accordingly. On push to `main`, the image is built and deployed automatically.

## Reference

- Implementation Guide: https://minvws.github.io/generiekefuncties-docs
- Input Script: https://github.com/minvws/generiekefuncties-docs/discussions/32
- Hackathon Info: https://github.com/minvws/generiekefuncties-docs/discussions/34
