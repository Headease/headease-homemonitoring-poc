output "cluster_endpoint" {
  description = "GKE cluster endpoint"
  value       = google_container_cluster.primary.endpoint
  sensitive   = true
}

output "namespace" {
  description = "Kubernetes namespace"
  value       = kubernetes_namespace_v1.headease.metadata[0].name
}

output "helm_release_status" {
  description = "Helm release status"
  value       = helm_release.headease_homemonitoring.status
}
