replicaCount: 1

image:
  repository: "${image_repository}"
  tag: "${image_tag}"
  pullPolicy: Always

ingress:
  enabled: true
  className: nginx
  fhirHost: "${fhir_host}"
  adminHost: "${admin_host}"

config:
  fhirBaseUrl: "${fhir_base_url}"
  lrzaBaseUrl: "https://adressering.proeftuin.gf.irealisatie.nl/poc/FHIR/fhir"
  nviBaseUrl: "https://nvi.proeftuin.gf.irealisatie.nl"
  prsBaseUrl: "https://pseudoniemendienst.proeftuin.gf.irealisatie.nl"
  oauthBaseUrl: "https://oauth.proeftuin.gf.irealisatie.nl"
  uraNumber: "${ura_number}"
  organizationName: "${organization_name}"
  nviUraNumber: "90000901"

certificates:
  existingSecret: "${cert_secret_name}"

resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 256Mi
