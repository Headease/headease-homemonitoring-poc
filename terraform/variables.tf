variable "project" {
  description = "GCP project ID"
  type        = string
  default     = "cumuluz-vws-hackathon-april-26"
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "europe-west4"
}

variable "cluster_name" {
  description = "GKE cluster name"
  type        = string
  default     = "headease-homemonitoring"
}

variable "node_machine_type" {
  description = "GKE node machine type"
  type        = string
  default     = "e2-standard-2"
}

variable "namespace" {
  description = "Kubernetes namespace for the deployment"
  type        = string
  default     = "headease-homemonitoring"
}

variable "image_repository" {
  description = "Docker image repository"
  type        = string
  default     = "europe-west4-docker.pkg.dev/cumuluz-vws-hackathon-april-26/headease/headease-homemonitoring"
}

variable "image_tag" {
  description = "Docker image tag (should match pyproject.toml version)"
  type        = string
  default     = "0.4.2"
}

variable "host" {
  description = "Ingress hostname"
  type        = string
  default     = "data-source.gf-cumuluz-poc.headease.nl"
}

variable "fhir_base_url" {
  description = "Public FHIR base URL (derived from host)"
  type        = string
  default     = ""
}

variable "ura_number" {
  description = "Organization URA number"
  type        = string
  default     = "90000315"
}

variable "organization_name" {
  description = "Organization display name"
  type        = string
  default     = "HeadEase"
}

variable "letsencrypt_email" {
  description = "Email for Let's Encrypt certificate notifications"
  type        = string
  default     = "roland@headease.nl"
}

variable "cert_secret_name" {
  description = "Name of an existing Kubernetes Secret containing the mTLS certificates"
  type        = string
  default     = "headease-homemonitoring-certs"
}
