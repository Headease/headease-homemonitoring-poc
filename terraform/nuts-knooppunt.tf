resource "helm_release" "nuts_knooppunt" {
  name       = "nuts-knooppunt"
  repository = "oci://ghcr.io/nuts-foundation"
  chart      = "helm-nuts-knooppunt"
  version    = "0.11.0"
  namespace  = kubernetes_namespace_v1.headease.metadata[0].name

  values = [templatefile("${path.module}/nuts-knooppunt-values.yaml.tpl", {
    base_domain = var.base_domain
  })]

  depends_on = [kubernetes_namespace_v1.headease]
}
