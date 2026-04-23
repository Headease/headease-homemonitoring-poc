# NUTS Knooppunt deployment
# NUTS node and HAPI FHIR are disabled — we use our own FHIR service

replicaCount: 1

image:
  repository: ghcr.io/nuts-foundation/nuts-knooppunt
  pullPolicy: IfNotPresent
  tag: "0.11.0"

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

# Mount our certificates
extraVolumes:
  - name: certs
    secret:
      secretName: headease-homemonitoring-certs

extraVolumeMounts:
  - name: certs
    mountPath: /certs
    readOnly: true

# Knooppunt application configuration
config:
  strictmode: false

  # HTTP interface
  http:
    public:
      address: ":8080"
    internal:
      address: ":8081"

  # Authentication to MinVWS proeftuin services (mTLS + OAuth)
  authn:
    minvws:
      tokenendpoint: "https://oauth.proeftuin.gf.irealisatie.nl/oauth/token"
      tlscertfile: "/certs/uzi-chain.crt"
      tlskeyfile: "/certs/private.key"

  # Addressing / mCSD — uses proeftuin LRZa
  mcsd:
    admin:
      root:
        fhirbaseurl: "https://adressering.proeftuin.gf.irealisatie.nl/poc/FHIR/fhir"

  # Pseudonymization — uses proeftuin PRS
  pseudo:
    prsurl: "https://pseudoniemendienst.proeftuin.gf.irealisatie.nl"

  # NVI (Nationale Verwijsindex)
  nvi:
    baseurl: "https://nvi.proeftuin.gf.irealisatie.nl"
    audience: "90000901"

resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 256Mi
