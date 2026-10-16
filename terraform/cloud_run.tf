resource "google_cloud_run_v2_service" "backend" {
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.backend_sa.email

    # Free tier: keep max instances low and allow scale-to-zero (no min_instance_count)
    # so you pay/consume nothing while idle. Cloud Run's always-free tier covers
    # 2M requests/month, 360k GB-seconds, 180k vCPU-seconds - plenty for a portfolio demo.
    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      image = var.backend_image

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      ports {
        container_port = 8080
      }

      env {
        name = "OPENAI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.openai_api_key.secret_id
            version = "latest"
          }
        }
      }

      env {
        name  = "ENVIRONMENT"
        value = "production"
      }
    }
  }

  depends_on = [
    google_project_service.run,
    google_secret_manager_secret_version.openai_api_key,
  ]
}

# Allow public (unauthenticated) access if requested - typical for a portfolio demo API
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  count    = var.allow_unauthenticated ? 1 : 0
  location = google_cloud_run_v2_service.backend.location
  name     = google_cloud_run_v2_service.backend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
