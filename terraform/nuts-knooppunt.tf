resource "helm_release" "nuts_knooppunt" {
  name             = "nuts-knooppunt"
  chart            = "${path.module}/../../NUTS/nuts-knooppunt/helm/nuts-knooppunt"
  namespace        = kubernetes_namespace_v1.headease.metadata[0].name
  create_namespace = false

  values = [templatefile("${path.module}/nuts-knooppunt-values.yaml.tpl", {
    host = var.host
  })]

  depends_on = [kubernetes_namespace_v1.headease]
}
