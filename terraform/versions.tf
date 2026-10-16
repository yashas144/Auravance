terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.30"
    }
  }

  # Optional: use a GCS backend for remote state instead of local state.
  # Uncomment and set your own bucket (create it manually first, it's free-tier eligible at low usage):
  # backend "gcs" {
  #   bucket = "auravance-tfstate"
  #   prefix = "terraform/state"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region

  # The firebase.googleapis.com API rejects plain end-user ADC credentials
  # (a documented provider limitation). Impersonating a service account
  # works around it. Create the SA and grant yourself
  # roles/iam.serviceAccountTokenCreator on it first (see README-DEPLOY.md).
  impersonate_service_account = "tf-firebase-bootstrap@${var.project_id}.iam.gserviceaccount.com"
}
