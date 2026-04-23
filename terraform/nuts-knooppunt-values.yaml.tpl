# NUTS Knooppunt deployment
# NUTS node and HAPI FHIR are disabled — we use our own FHIR service

replicaCount: 1

image:
  repository: ghcr.io/nuts-foundation/nuts-knooppunt
  pullPolicy: IfNotPresent

# Disable sub-charts we don't need
fhir:
  enabled: false
nuts:
  enabled: false
pep:
  enabled: false
mock-vc-issuer:
  enabled: false
jaeger:
  enabled: false

# Knooppunt application configuration
config:
  # HTTP interface
  http:
    internal:
      address: ":1323"
    public:
      address: ":1324"

  # mCSD (Care Services Directory) — uses our LRZa registration
  mcsd:
    fhirBaseUrl: "https://adressering.proeftuin.gf.irealisatie.nl/poc/FHIR/fhir"

  # Pseudonymization — uses proeftuin PRS
  pseudonymization:
    enabled: true
    prsBaseUrl: "https://pseudoniemendienst.proeftuin.gf.irealisatie.nl"

  # NVI (Nationale Verwijsindex)
  nvi:
    enabled: true
    baseUrl: "https://nvi.proeftuin.gf.irealisatie.nl"

resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 256Mi
