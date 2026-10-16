variable "project_id" {
  description = "GCP project ID to deploy into"
  type        = string
}

variable "region" {
  description = "GCP region for Cloud Run and Artifact Registry (choose one close to you, e.g. us-central1)"
  type        = string
  default     = "us-central1"
}

variable "service_name" {
  description = "Name for the Cloud Run backend service"
  type        = string
  default     = "auravance-backend"
}

variable "backend_image" {
  description = "Full container image path in Artifact Registry, e.g. us-central1-docker.pkg.dev/<project_id>/auravance/backend:latest"
  type        = string
}

variable "openai_api_key" {
  description = "OpenAI API key, stored in Secret Manager (never written to state in plaintext beyond this one apply)"
  type        = string
  sensitive   = true
}

variable "allow_unauthenticated" {
  description = "Whether the Cloud Run service is publicly accessible without auth. true = public demo API."
  type        = bool
  default     = true
}
