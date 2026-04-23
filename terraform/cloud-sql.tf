data "google_compute_network" "default" {
  name = "default"
}

# Reserved private IP range for Cloud SQL peering
resource "google_compute_global_address" "private_ip_range" {
  name          = "${var.cluster_name}-sql-private-ip-range"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = data.google_compute_network.default.id
}

# VPC peering for Cloud SQL private connectivity
resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = data.google_compute_network.default.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_range.name]
}

resource "google_sql_database_instance" "hapi" {
  name                = "${var.cluster_name}-hapi-db-v2"
  database_version    = "POSTGRES_17"
  region              = var.region
  deletion_protection = false

  settings {
    tier              = var.db_tier
    edition           = "ENTERPRISE"
    availability_type = "ZONAL"

    ip_configuration {
      ipv4_enabled    = false
      private_network = data.google_compute_network.default.id
      ssl_mode        = "ENCRYPTED_ONLY"
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

  depends_on = [google_service_networking_connection.private_vpc_connection]
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
    jdbc-url = "jdbc:postgresql://${google_sql_database_instance.hapi.private_ip_address}:5432/${google_sql_database.hapi.name}?sslmode=require"
    username = google_sql_user.hapi.name
    password = random_password.hapi_db.result
  }

  depends_on = [google_sql_user.hapi]
}
