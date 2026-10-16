output "backend_url" {
  description = "Public URL of the deployed FastAPI backend on Cloud Run"
  value       = google_cloud_run_v2_service.backend.uri
}

output "artifact_registry_repo" {
  description = "Full path to push your backend Docker image to"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.auravance.repository_id}"
}

output "backend_service_account" {
  description = "Service account email used by the Cloud Run backend"
  value       = google_service_account.backend_sa.email
}
