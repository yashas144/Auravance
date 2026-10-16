resource "google_artifact_registry_repository" "auravance" {
  repository_id = "auravance"
  location      = var.region
  format        = "DOCKER"
  description   = "Container images for the Auravance backend"

  depends_on = [google_project_service.artifact_registry]
}
