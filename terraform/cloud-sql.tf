resource "google_sql_database_instance" "hapi" {
  name                = "${var.cluster_name}-hapi-db"
  database_version    = "POSTGRES_17"
  region              = var.region
  deletion_protection = false

  settings {
    tier              = var.db_tier
    edition           = "ENTERPRISE"
    availability_type = "ZONAL"

    # PoC: public IP with SSL required and open authorized networks.
    # Production would use private IP via VPC peering with a GKE-native peering config.
    ip_configuration {
      ipv4_enabled = true
      ssl_mode     = "ENCRYPTED_ONLY"
      authorized_networks {
        name  = "allow-all"
        value = "0.0.0.0/0"
      }
    }

    backup_configuration {
      enabled = false
    }

    database_flags {
      name  = "max_connections"
      value = "100"
    }

    # Kill connections stuck in "idle in transaction" after 2 minutes.
    # Prevents HAPI transactions from holding connections indefinitely.
    database_flags {
      name  = "idle_in_transaction_session_timeout"
      value = "120000"
    }
  }

}

resource "google_sql_database" "hapi" {
  name     = "hapi"
  instance = google_sql_database_instance.hapi.name
}

resource "random_password" "hapi_db" {
  length  = 24
  special = false
}

resource "google_sql_user" "hapi" {
  name     = "hapi"
  instance = google_sql_database_instance.hapi.name
  password = random_password.hapi_db.result
}

resource "kubernetes_secret_v1" "hapi_db" {
  metadata {
    name      = "hapi-db"
    namespace = kubernetes_namespace_v1.headease.metadata[0].name
  }

  data = {
    jdbc-url = "jdbc:postgresql://${google_sql_database_instance.hapi.public_ip_address}:5432/${google_sql_database.hapi.name}?sslmode=require"
    username = google_sql_user.hapi.name
    password = random_password.hapi_db.result
  }

  depends_on = [google_sql_user.hapi]
}
