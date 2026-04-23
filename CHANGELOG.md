# Changelog

All notable changes to this project will be documented in this file.

## [0.2.0] - 2026-04-23

### Added
- NVI registration via FHIR List API (`POST /v1-poc/fhir/List`)
- NVI check endpoint (`GET /admin/nvi-check?bsn=...`)
- OAuth token endpoint (`GET /admin/token?service=nvi|prs`)
- OPRF pseudonymisation with pysodium ristretto255
- Outgoing HTTP request/response logging
- Idempotent LRZa registration (search + upsert)
- BSN identifier support in Observation `$lastn` patient parameter
- Dockerfile (multi-stage, linux/amd64)
- Helm chart with configmap, secrets, ingress
- Terraform deployment (GKE, nginx ingress, cert-manager, Let's Encrypt)
- GitHub Actions CI/CD (build, push, deploy)
- Data User Guide (`docs/DATA-USER-GUIDE.md`)
- Data Holder Script (`docs/SCRIPT.md`)

### Changed
- URA number corrected to `90000315` (from UZI certificate SAN)
- PRS recipient set to NVI (URA `90000901`, scope `nationale-verwijsindex`)
- LDN cert used for mTLS, UZI cert for JWT signing
- Public URL changed from `ngrok.headease.nl` to `data-source.gf-cumuluz-poc.headease.nl`

### Fixed
- PRS response field is `jwe` (not `evaluated_output`)
- PRS API uses camelCase fields (`encryptedPersonalId`, not `blinded_input`)
- Intermediate `.cer` files handled as DER (not PEM)
- Endpoint search uses `organization.identifier` (not `managingOrganization.identifier`)

## [0.1.0] - 2026-04-22

### Added
- Initial FastAPI app with FHIR Patient and Observation endpoints
- Sample data seeding (BSN `004895708`, BloodPressure, BodyWeight)
- LRZa registration (Organization + Endpoints)
- Authorization header verification on FHIR endpoints
