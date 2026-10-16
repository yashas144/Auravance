# Deploying Auravance to GCP (Free Tier) with Terraform

Architecture: **Cloud Run** (backend, scale-to-zero, always-free tier) + **Firebase Hosting** (frontend, free static hosting) + **Secret Manager** (API keys) + **Artifact Registry** (container images).

Estimated cost for portfolio-level traffic: **$0/month**, within GCP's Always Free tier limits (2M Cloud Run requests/mo, 10GB Hosting storage/mo, 6 active secrets).

## Prerequisites

1. A GCP account with billing enabled (required even for free tier, but you won't be charged within free limits).
2. Install: `gcloud` CLI, `terraform` (>=1.5), `docker`, `firebase-tools` (`npm install -g firebase-tools`).
3. Create/select a GCP project:
   ```bash
   gcloud projects create auravance-demo --name="Auravance Demo"
   gcloud config set project auravance-demo
   gcloud auth application-default login
   ```
4. Enable billing on the project via the GCP Console (Billing → Link a billing account) — Terraform needs this to enable APIs.

## Step 1 — Build and push the backend container

```bash
cd backend
cp ../terraform/Dockerfile.backend ./Dockerfile

# One-time: create the Artifact Registry repo (Terraform also defines this,
# but you need it before your first image push, so create it manually first
# OR run `terraform apply -target=google_artifact_registry_repository.auravance` first)
gcloud artifacts repositories create auravance \
  --repository-format=docker \
  --location=us-central1

gcloud auth configure-docker us-central1-docker.pkg.dev

docker build -t us-central1-docker.pkg.dev/auravance-demo/auravance/backend:latest .
docker push us-central1-docker.pkg.dev/auravance-demo/auravance/backend:latest
```

## Step 2 — Terraform init and apply

```bash
cd ../terraform
terraform init

terraform plan \
  -var="project_id=auravance-demo" \
  -var="backend_image=us-central1-docker.pkg.dev/auravance-demo/auravance/backend:latest" \
  -var="openai_api_key=sk-..."

terraform apply \
  -var="project_id=auravance-demo" \
  -var="backend_image=us-central1-docker.pkg.dev/auravance-demo/auravance/backend:latest" \
  -var="openai_api_key=sk-..."
```

Better: put these in a `terraform.tfvars` file (add it to `.gitignore` — it contains your API key) instead of passing `-var` flags each time:

```hcl
# terraform.tfvars (DO NOT COMMIT)
project_id     = "auravance-demo"
region         = "us-central1"
backend_image  = "us-central1-docker.pkg.dev/auravance-demo/auravance/backend:latest"
openai_api_key = "sk-..."
```

Then just run `terraform apply`.

After apply finishes, grab your backend URL:

```bash
terraform output backend_url
```

## Step 3 — Deploy the frontend to Firebase Hosting

```bash
cd ../frontend

# Point the frontend at your deployed backend URL
echo "VITE_API_BASE_URL=$(cd ../terraform && terraform output -raw backend_url)" > .env.production

npm install
npm run build

firebase login
firebase init hosting   # select the existing GCP project, public dir = "dist"
firebase deploy --only hosting
```

## Step 4 — Verify

- Backend health check: `curl <backend_url>/health` (adjust to your actual health route)
- Frontend: open the Firebase Hosting URL printed after deploy
- Check GCP Console → Cloud Run → your service → confirm request count and that it scales to zero when idle

## Staying within free tier

- **Cloud Run**: `min_instance_count = 0` (already set) means you pay nothing while idle. Don't set a minimum unless you want always-warm instances (that costs money).
- **Secret Manager**: free tier covers 6 active secret versions and 10k access operations/month — one secret is well within this.
- **Artifact Registry**: 0.5GB storage free; your image should be well under that given your small model artifacts.
- **Firebase Hosting**: 10GB storage + 360MB/day transfer free — plenty for a React SPA.

## Tearing down

To avoid any drift toward paid tiers if traffic grows unexpectedly:

```bash
terraform destroy \
  -var="project_id=auravance-demo" \
  -var="backend_image=us-central1-docker.pkg.dev/auravance-demo/auravance/backend:latest" \
  -var="openai_api_key=sk-..."

firebase hosting:disable
```
