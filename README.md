# HeadEase Home Monitoring PoC

Data Holder implementation for the GF Proeftuin Home Monitoring use case (hackathon April 2026).

HeadEase acts as a **data holder**, making patient health data (BloodPressure, BodyWeight) available to data users via FHIR endpoints, discoverable through the LRZa adressering service and NVI nationale verwijsindex.

## Architecture

This PoC implements the data holder steps from the [home monitoring input script](https://github.com/minvws/generiekefuncties-docs/discussions/32):

1. **Register** Organization + Endpoints at the LRZa
2. **Pseudonymise** patient BSNs via the PRS (OPRF blinding + HKDF)
3. **Register localization records** at the NVI with pseudonymised identifiers
4. **Serve FHIR data** — Patient search by BSN, Observation `$lastn` for BloodPressure and BodyWeight
5. **Verify authorization** — required headers on incoming requests

## Stack

- Python 3.12+, FastAPI, Uvicorn
- pyoprf / liboprf (OPRF blinding)
- httpx (mTLS outbound calls)
- cryptography (HKDF derivation)
- PyJWT (OAuth client assertions)

## Running locally with Docker

```bash
# Build the image (includes liboprf)
docker build --platform linux/amd64 -t headease-homemonitoring:latest .

# Start Redis
docker run -d --name headease-redis -p 6379:6379 redis:7-alpine

# Run with certificates and .env
docker run --rm -p 8000:8000 \
  --link headease-redis:redis \
  -v $(pwd)/certificates:/certs:ro \
  --env-file .env \
  -e HEADEASE_REDIS_URL=redis://redis:6379 \
  -e HEADEASE_CLIENT_CERT=/certs/headease-certificates-proeftuin/headease-uzi-external-intermediate/headease-uzi-chain.crt \
  -e HEADEASE_CLIENT_KEY=/certs/headease_nvi_20260202_145627.key \
  -e HEADEASE_UZI_CERT=/certs/headease-certificates-proeftuin/headease-uzi-external-intermediate/headease-uzi.crt \
  -e HEADEASE_UZI_INTERMEDIATE_CERT=/certs/gfmodules-test-uzi-external-intermediate.cer \
  -e HEADEASE_LDN_CERT=/certs/headease-certificates-proeftuin/headease-ldn-external-intermediate/headease-ldn.crt \
  -e HEADEASE_LDN_CHAIN_CERT=/certs/headease-certificates-proeftuin/headease-ldn-external-intermediate/headease-ldn-chain.crt \
  -e HEADEASE_LDN_CA_CERT=/certs/headease-certificates-proeftuin/headease-ldn-external-intermediate/ldn-ca.crt \
  headease-homemonitoring:latest
```

The app is available at `http://localhost:8000`.

## Development setup (without Docker)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

> **Note:** Requires `liboprf` and `libsodium` installed locally. See the [Dockerfile](Dockerfile) for build steps.

## API Endpoints

### Data Holder FHIR API (`/fhir`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/fhir/Patient/_search` | Search patient by BSN identifier |
| GET | `/fhir/Observation/$lastn` | Get latest observations by code and patient (ID or BSN) |

### Admin (`/admin`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/admin/register` | Register Organization + Endpoints at LRZa |
| POST | `/admin/register-nvi` | Pseudonymise BSN + register List at NVI |
| GET | `/admin/nvi-check` | Check NVI registration for a BSN |
| GET | `/admin/token` | Get OAuth Bearer token (service=nvi or service=prs) |

### Authorization

FHIR endpoints require these headers:
- `x-ura-identifier`
- `x-healthcareproviderroletype`
- `x-dezi-identifier`
- `x-dezi-roletype`

## Certificates

Client certificates for mTLS are in `certificates/` (not committed). Two certificate chains:

- **UZI** — for signing JWT client assertions (contains URA number)
- **LDN** — for mTLS connections to proeftuin services

## Configuration

Environment variables (prefix `HEADEASE_`), see `.env.example` for all options:

| Variable | Default | Description |
|----------|---------|-------------|
| `HEADEASE_FHIR_BASE_URL` | `https://data-source.gf-cumuluz-poc.headease.nl/fhir` | Public FHIR base URL |
| `HEADEASE_LRZA_BASE_URL` | `https://adressering.proeftuin.gf.irealisatie.nl/poc/FHIR/fhir` | LRZa service URL |
| `HEADEASE_NVI_BASE_URL` | `https://nvi.proeftuin.gf.irealisatie.nl` | NVI service URL |
| `HEADEASE_PRS_BASE_URL` | `https://pseudoniemendienst.proeftuin.gf.irealisatie.nl` | PRS service URL |
| `HEADEASE_OAUTH_BASE_URL` | `https://oauth.proeftuin.gf.irealisatie.nl` | OAuth service URL |
| `HEADEASE_URA_NUMBER` | `90000315` | Our organization URA identifier |
| `HEADEASE_NVI_URA_NUMBER` | `90000901` | NVI URA (PRS recipient) |

## Deployment

See [terraform/README.md](terraform/README.md) for GKE deployment with Terraform, Helm, and GitHub Actions CI/CD.

## Documentation

- [Data Holder Script](docs/SCRIPT.md) — step-by-step hackathon script
- [Data User Guide](docs/DATA-USER-GUIDE.md) — instruction document for data users

## Sample Data

The app seeds one patient (BSN `004895708`) with 3 blood pressure and 3 body weight observations on startup.

## License

[MIT](LICENSE)
