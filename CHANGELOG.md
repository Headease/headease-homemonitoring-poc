# Changelog

All notable changes to this project will be documented in this file.

## [0.11.3] - 2026-04-24

### Fixed
- FHIR proxy strips `Content-Encoding` header so httpx-decompressed bodies aren't double-decoded by clients
- Token endpoint: JWT `aud` is the token endpoint URL (per RFC 7523); target service is checked via `target_audience` claim
- Seeder waits up to 5 minutes for HAPI readiness (Cloud SQL cold starts)
- Data-user script filters `$lastn` observations client-side by LOINC code

### Added
- `POST /internal/seed` endpoint on FHIR service for manual HAPI sample-data trigger
- Cloud SQL instance renamed to `-v2` with `db-g1-small` tier for faster provisioning

## [0.11.1] - 2026-04-24

### Changed
- Default FHIR base URL switched from `ngrok.headease.nl` to `data-source.gf-cumuluz-poc.headease.nl` across config, Helm values, docs, and examples

## [0.11.0] - 2026-04-23

### Added
- Cloud SQL PostgreSQL (db-f1-micro) as HAPI backing database
- VPC peering via `google_service_networking_connection` for private IP connectivity
- Terraform-generated random password stored in K8s secret `hapi-db`
- HAPI Helm deployment conditionally wires PostgreSQL from secret when `hapi.database.enabled`

### Changed
- HAPI uses Cloud SQL when deployed via Terraform; H2 embedded when via docker-compose
- Chart version bumped to 0.7.0

### Required
- APIs: `sqladmin.googleapis.com`, `servicenetworking.googleapis.com`, `compute.googleapis.com`
- IAM roles on deploy SA: `cloudsql.admin`, `servicenetworking.networksAdmin`

## [0.10.1] - 2026-04-23

### Changed
- docker-compose wires nuts-knooppunt `KNPT_MCSD_QUERY_FHIRBASEURL` to our HAPI
- HAPI data persisted in a named volume across restarts

## [0.10.0] - 2026-04-23

### Changed
- Replaced custom in-memory FHIR implementation with a proxy to HAPI FHIR
- Bearer token check at the proxy; HAPI handles all FHIR logic, search, and persistence
- Sample data seeded into HAPI on startup (idempotent)

### Added
- HAPI FHIR server to docker-compose (`hapi-fhir` service on port 8082)
- HAPI FHIR Deployment + Service in Helm chart (`hapi.enabled`)
- Helm chart version bumped to 0.6.0 (added HAPI deployment)

## [0.9.0] - 2026-04-23

### Added
- Admin ingress at `admin.<base_domain>` (separate from FHIR service)
- `base_domain` variable replaces `host` — derives `data-source.` and `admin.` subdomains

### Changed
- FHIR service at `data-source.<base_domain>`, admin at `admin.<base_domain>`
- Ingress serves both hosts with shared TLS certificate
- Helm chart version bumped to 0.5.0

## [0.8.0] - 2026-04-23

### Added
- NVI endpoints via nuts-knooppunt (`/admin/register-nvi-nk`, `/admin/nvi-check-nk`)
- nuts-knooppunt handles pseudonymisation transparently (plain BSN in, pseudonym out)
- Parallel endpoints allow comparing direct vs knooppunt NVI implementations
- nuts-knooppunt Helm chart configured with mTLS certs and proeftuin service URLs

## [0.7.0] - 2026-04-23

### Added
- nuts-knooppunt Helm chart deployment via Terraform (OCI chart v0.11.0)
- Configured with mTLS certs, OAuth, LRZa, PRS, and NVI proeftuin services
- NUTS node, HAPI FHIR, PEP, mock-vc-issuer, Jaeger all disabled

## [0.6.0] - 2026-04-23

### Added
- Split into FHIR service and Admin service (same image, different entrypoints)
- `app.main_fhir:app` — public FHIR endpoints + `/oauth2/token`
- `app.main_admin:app` — registration, NVI, proeftuin tokens
- docker-compose runs both services on ports 8000 and 8001

### Changed
- Helm chart deploys two Deployments and Services (fhir + admin)
- Ingress points to FHIR service only
- Dockerfile uses `APP_MODULE` env var for entrypoint selection
- Helm chart version bumped to 0.4.0

## [0.5.0] - 2026-04-23

### Added
- OAuth token endpoint (`POST /oauth2/token`) with JWT client assertion validation
- x5c certificate chain verification against trusted LDN CA
- Redis-backed token store with configurable TTL
- FHIR endpoints accept Bearer tokens (validated against Redis)
- docker-compose.yml for local development (app + Redis)

### Changed
- Authorization headers on `/oauth2/token` are optional (stored if present)
- FHIR endpoints fall back to header-only auth when no Bearer token provided

## [0.4.1] - 2026-04-23

### Added
- Organization.endpoint references to both FHIR and OAuth Endpoints (JSON Patch)
- Endpoint.managingOrganization includes both reference and identifier
- LRZa cleanup script (`scripts/cleanup-lrza.sh`)
- NVI check endpoint (`GET /admin/nvi-check`)

### Fixed
- Endpoint upsert searches by name instead of unsupported chained params
- NVI check uses correct NVI_IDENTIFIER_SYSTEM

## [0.4.0] - 2026-04-23

### Changed
- Switched from custom pysodium OPRF blinding to `pyoprf.blind` (liboprf) for correct RFC-compatible pseudonyms
- Dockerfile builds liboprf from source for pyoprf compatibility

### Fixed
- Pseudonyms now match the reference implementation, making NVI registrations queryable

## [0.3.2] - 2026-04-23

### Fixed
- NVI check uses JWE pseudonym as `subject:identifier` value, not the full packaged NVI identifier

## [0.3.1] - 2026-04-23

### Changed
- Register both `Patient` and `ObservationVitalSigns` data categories at the NVI
- NVI check query uses `nvi-pseudonym` NamingSystem for `subject:identifier`
- Updated DATA-USER-GUIDE with correct NVI query system and both data categories

## [0.3.0] - 2026-04-23

### Added
- GitHub Actions CI/CD workflow (build, push, deploy)
- Let's Encrypt TLS via cert-manager
- Nginx ingress controller in Terraform
- MIT license

### Changed
- NVI registration switched from NVIDataReference to FHIR List API (`/v1-poc/fhir/List`)
- NVI check uses `nvi-pseudonym` NamingSystem for `subject:identifier` queries
- Removed `nvi-locate`, `nvi-registrations`, `register-nvi-list` endpoints
- SCRIPT.md uses `$BASE_URL` variable (default `data-source.gf-cumuluz-poc.headease.nl`)
- Docker image tagged with version from `pyproject.toml` instead of git SHA
- GKE cluster changed to zonal (single node) instead of regional (3 nodes)

### Fixed
- Endpoint search uses `organization.identifier` for LRZa upsert
- `backend.tf` removed unsupported `project` argument
- Terraform uses `kubernetes_namespace_v1` (not deprecated `kubernetes_namespace`)

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
