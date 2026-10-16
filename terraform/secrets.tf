resource "google_secret_manager_secret" "openai_api_key" {
  secret_id = "openai-api-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.secret_manager]
}

resource "google_secret_manager_secret_version" "openai_api_key" {
  secret      = google_secret_manager_secret.openai_api_key.id
  secret_data = var.openai_api_key
}

# Dedicated service account for the Cloud Run service, so we grant it
# only what it needs (least privilege) rather than using the default compute SA.
resource "google_service_account" "backend_sa" {
  account_id   = "auravance-backend-sa"
  display_name = "Auravance backend Cloud Run service account"
}

resource "google_secret_manager_secret_iam_member" "backend_sa_secret_access" {
  secret_id = google_secret_manager_secret.openai_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.backend_sa.email}"
}
