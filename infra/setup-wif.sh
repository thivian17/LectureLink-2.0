#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# LectureLink V2 — Workload Identity Federation (WIF) Setup
# ---------------------------------------------------------------------------
#
# This is a ONE-TIME manual setup script. It is NOT run by CI.
#
# It configures Google Cloud so that GitHub Actions can authenticate
# using Workload Identity Federation (WIF) instead of long-lived
# service account keys.
#
# Prerequisites:
#   - gcloud CLI installed and authenticated as a project owner
#   - The target GCP project already exists
#
# Usage:
#   chmod +x infra/setup-wif.sh
#   ./infra/setup-wif.sh
#
# After running, copy the printed WIF_PROVIDER and WIF_SERVICE_ACCOUNT
# values into your GitHub repository secrets.
# ---------------------------------------------------------------------------

set -euo pipefail

# ---- Configuration (edit these) -------------------------------------------
PROJECT_ID="lecturelink-prod"
REGION="us-central1"
GITHUB_ORG="thivian17"      # ← Replace with your GitHub org or username
REPO_NAME="LectureLink-2.0"        # ← Replace with your repository name

POOL_ID="github-pool"
PROVIDER_ID="github-provider"
SA_NAME="github-deployer"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
# ---------------------------------------------------------------------------

echo "==> Setting active project to ${PROJECT_ID}"
gcloud config set project "${PROJECT_ID}"

# Step 1: Enable required APIs
echo ""
echo "==> Enabling required APIs..."
gcloud services enable \
  iamcredentials.googleapis.com \
  iam.googleapis.com \
  cloudresourcemanager.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  cloudtasks.googleapis.com

# Step 2: Create a Workload Identity Pool
#
# A pool groups external identities (GitHub Actions in our case).
# We create one pool per trust domain.
echo ""
echo "==> Creating Workload Identity Pool: ${POOL_ID}"
gcloud iam workload-identity-pools create "${POOL_ID}" \
  --project="${PROJECT_ID}" \
  --location="global" \
  --display-name="GitHub Actions Pool" \
  --description="WIF pool for GitHub Actions CI/CD" \
  || echo "   (pool may already exist — continuing)"

# Step 3: Create an OIDC Provider inside the pool
#
# This tells Google Cloud to trust JWTs issued by GitHub's OIDC provider.
# The attribute mapping translates GitHub token claims into Google attributes:
#   - google.subject    = unique identity (e.g. repo:org/repo:ref:refs/heads/main)
#   - attribute.repository = the full repo name (org/repo)
echo ""
echo "==> Creating OIDC Provider: ${PROVIDER_ID}"
gcloud iam workload-identity-pools providers create-oidc "${PROVIDER_ID}" \
  --project="${PROJECT_ID}" \
  --location="global" \
  --workload-identity-pool="${POOL_ID}" \
  --display-name="GitHub OIDC Provider" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository == '${GITHUB_ORG}/${REPO_NAME}'" \
  || echo "   (provider may already exist — continuing)"

# Step 4: Create the deployer service account
#
# This is the identity that GitHub Actions will impersonate.
# It needs just enough permissions to build, push, and deploy.
echo ""
echo "==> Creating service account: ${SA_EMAIL}"
gcloud iam service-accounts create "${SA_NAME}" \
  --project="${PROJECT_ID}" \
  --display-name="GitHub Actions Deployer" \
  --description="Used by GitHub Actions via WIF to deploy to Cloud Run" \
  || echo "   (service account may already exist — continuing)"

# Step 5: Grant IAM roles to the service account
#
# roles/run.admin              — deploy and manage Cloud Run services
# roles/artifactregistry.writer — push Docker images to Artifact Registry
# roles/iam.serviceAccountUser — act as the Cloud Run runtime service account
# roles/secretmanager.viewer   — list secrets (needed for --set-secrets flag)
echo ""
echo "==> Granting IAM roles to ${SA_EMAIL}..."

ROLES=(
  "roles/run.admin"
  "roles/artifactregistry.writer"
  "roles/iam.serviceAccountUser"
  "roles/secretmanager.viewer"
)

for ROLE in "${ROLES[@]}"; do
  echo "   - ${ROLE}"
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${ROLE}" \
    --condition=None \
    --quiet
done

# Step 6: Allow the WIF pool to impersonate the service account
#
# This is the critical binding: it says "tokens from GitHub Actions
# (specifically from our repo) are allowed to act as this SA."
echo ""
echo "==> Binding WIF pool to service account..."

POOL_FULL_ID="projects/${PROJECT_ID}/locations/global/workloadIdentityPools/${POOL_ID}"

gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
  --project="${PROJECT_ID}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/${POOL_FULL_ID}/attribute.repository/${GITHUB_ORG}/${REPO_NAME}"

# Step 7: Create the Artifact Registry repository (if it doesn't exist)
echo ""
echo "==> Creating Artifact Registry repository: lecturelink"
gcloud artifacts repositories create lecturelink \
  --repository-format=docker \
  --location="${REGION}" \
  --description="LectureLink Docker images" \
  || echo "   (repository may already exist — continuing)"

# ---------------------------------------------------------------------------
# Print the values to set as GitHub secrets
# ---------------------------------------------------------------------------
echo ""
echo "==========================================================================="
echo " WIF setup complete!"
echo "==========================================================================="
echo ""
echo " Add these as GitHub repository secrets:"
echo ""

PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")
WIF_PROVIDER="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/providers/${PROVIDER_ID}"

echo "   WIF_PROVIDER           = ${WIF_PROVIDER}"
echo "   WIF_SERVICE_ACCOUNT    = ${SA_EMAIL}"
echo "   GCP_PROJECT_ID         = ${PROJECT_ID}"
echo ""
echo " Also set these secrets (from your Supabase dashboard):"
echo "   NEXT_PUBLIC_SUPABASE_URL"
echo "   NEXT_PUBLIC_SUPABASE_ANON_KEY"
echo "   NEXT_PUBLIC_API_URL        (Cloud Run API URL, after first deploy)"
echo ""
echo " And these in Google Secret Manager (used by Cloud Run at runtime):"
echo "   SUPABASE_URL"
echo "   SUPABASE_ANON_KEY"
echo "   SUPABASE_SERVICE_ROLE_KEY"
echo "   GEMINI_API_KEY"
echo "   INTERNAL_API_KEY"
echo "==========================================================================="
