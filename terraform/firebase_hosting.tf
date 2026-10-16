# Firebase Hosting requires a Firebase-enabled project. This creates the
# Hosting site resource; the actual frontend build deploy is done via the
# Firebase CLI (see README-DEPLOY.md), since Terraform doesn't push static
# file content to Hosting.

resource "google_firebase_project" "default" {
  provider = google-beta
  project  = var.project_id

  depends_on = [google_project_service.firebase]
}

resource "google_firebase_hosting_site" "frontend" {
  provider = google-beta
  project  = var.project_id
  site_id  = "${var.project_id}-frontend"

  depends_on = [
    google_firebase_project.default,
    google_project_service.firebase_hosting,
  ]
}

output "frontend_hosting_site_id" {
  description = "Firebase Hosting site ID - deploy your built frontend here with the Firebase CLI"
  value       = google_firebase_hosting_site.frontend.site_id
}
