locals {
  fhir_host  = "data-source.${var.base_domain}"
  admin_host = "admin.${var.base_domain}"
  fhir_url   = var.fhir_base_url != "" ? var.fhir_base_url : "https://${local.fhir_host}/fhir"
}

resource "kubernetes_namespace_v1" "headease" {
  metadata {
    name = var.namespace
    labels = {
      "app.kubernetes.io/managed-by" = "terraform"
      "app.kubernetes.io/part-of"    = "headease-homemonitoring"
    }
  }

  depends_on = [google_container_node_pool.primary]
}

resource "helm_release" "headease_homemonitoring" {
  name      = "headease-homemonitoring"
  chart     = "${path.module}/../helm/headease-homemonitoring"
  namespace = kubernetes_namespace_v1.headease.metadata[0].name

  values = [templatefile("${path.module}/values.yaml.tpl", {
    image_repository  = var.image_repository
    image_tag         = var.image_tag
    fhir_host         = local.fhir_host
    admin_host        = local.admin_host
    fhir_base_url     = local.fhir_url
    ura_number        = var.ura_number
    organization_name = var.organization_name
    cert_secret_name  = var.cert_secret_name
  })]

  depends_on = [kubernetes_namespace_v1.headease, helm_release.nginx_ingress]
}
