# Deploying LectureLink V2 to lecturelink.ca

Step-by-step guide to deploy LectureLink V2 on Google Cloud Run.

**Architecture:**
```
lecturelink.ca          → Cloud Run: lecturelink-web-prod   (Next.js)
api.lecturelink.ca      → Cloud Run: lecturelink-api-prod   (FastAPI)
                          Cloud Run: lecturelink-worker-prod (arq worker, same image as API)
                          Cloud Memorystore: Redis
                          Supabase: PostgreSQL + Auth + Storage (external)
```

---

## Prerequisites

- [Google Cloud CLI (`gcloud`)](https://cloud.google.com/sdk/docs/install) installed and authenticated
- [Docker](https://docs.docker.com/get-docker/) installed
- A GCP project (create one at https://console.cloud.google.com if you don't have one)
- A Supabase project (your existing one)
- The domain `lecturelink.ca` registered and accessible via your registrar's DNS panel
- A GitHub repository with this code pushed

Run this once to set your project:
```bash
gcloud auth login
gcloud config set project meeting-assistant-473703
```

Replace `YOUR_PROJECT_ID` everywhere below with your actual GCP project ID.

---

## Step 1: Enable GCP APIs

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  redis.googleapis.com \
  vpcaccess.googleapis.com \
  compute.googleapis.com \
  iam.googleapis.com
```

Wait ~30 seconds for APIs to activate.

---

## Step 2: Create Artifact Registry Repository

This stores your Docker images.

```bash
gcloud artifacts repositories create lecturelink \
  --repository-format=docker \
  --location=us-central1 \
  --description="LectureLink container images"
```

Verify:
```bash
gcloud artifacts repositories list --location=us-central1
```

---

## Step 3: Create VPC Connector

Cloud Run needs this to reach Cloud Memorystore (Redis is on a private VPC network).

```bash
gcloud compute networks vpc-access connectors create lecturelink-connector \
  --region=us-central1 \
  --range=10.8.0.0/28
```

Verify:
```bash
gcloud compute networks vpc-access connectors describe lecturelink-connector --region=us-central1
```

---

## Step 4: Create Cloud Memorystore Redis Instance

```bash
gcloud redis instances create lecturelink-redis \
  --size=1 \
  --region=us-central1 \
  --redis-version=redis_7_2 \
  --tier=basic
```

This takes 3-5 minutes. When done, get the IP:

```bash
gcloud redis instances describe lecturelink-redis \
  --region=us-central1 \
  --format='value(host)'
```

**Save this IP.** You'll use it as `REDIS_IP` in later steps. The full URL is `redis://<IP>:6379`.
10.139.150.251
---

## Step 5: Store Secrets in Google Secret Manager

The API loads these secrets at startup via `config/secrets.py`. Create each one:

```bash
# Required — Supabase credentials
echo -n "https://ncypmtimgxfiumlkzrrz.supabase.co" | gcloud secrets create SUPABASE_URL --data-file=-
echo -n "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5jeXBtdGltZ3hmaXVtbGt6cnJ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA1MTgyNzAsImV4cCI6MjA4NjA5NDI3MH0.rXedsmhVpCB5ru3yryEiJYwogBdQzETNdUGtdg7ONkU" | gcloud secrets create SUPABASE_ANON_KEY --data-file=-
echo -n "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5jeXBtdGltZ3hmaXVtbGt6cnJ6Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MDUxODI3MCwiZXhwIjoyMDg2MDk0MjcwfQ._0kNpTVVlV7th_zhY5ffvI5yh0j8dEdzDxbSk9xQbQE
" | gcloud secrets create SUPABASE_SERVICE_ROLE_KEY --data-file=-

# Required — LLM access (Gemini API key)
echo -n "YOUR_GEMINI_API_KEY" | gcloud secrets create GEMINI_API_KEY --data-file=-

# Required — Internal API key (generate a random UUID)
echo -n "$(uuidgen)" | gcloud secrets create INTERNAL_API_KEY --data-file=-
```

> **Tip:** If you prefer Vertex AI over a Gemini API key, skip `GEMINI_API_KEY`. The app will auto-detect ADC credentials and use Vertex AI when no API key is set.

Optional secrets (create only if you use these services):
```bash
echo -n "YOUR_SENTRY_DSN" | gcloud secrets create SENTRY_DSN --data-file=-
echo -n "YOUR_POSTHOG_KEY" | gcloud secrets create POSTHOG_API_KEY --data-file=-
echo -n "YOUR_LANGFUSE_KEY" | gcloud secrets create LANGFUSE_SECRET_KEY --data-file=-
echo -n "YOUR_RESEND_KEY" | gcloud secrets create RESEND_API_KEY --data-file=-
```

Verify:
```bash
gcloud secrets list
```

---

## Step 6: Create Service Accounts

You need two service accounts:
1. **github-deployer** — used by GitHub Actions to deploy
2. **lecturelink-runtime** — used by Cloud Run services at runtime

### 6a. Deploy service account (for GitHub Actions)

```bash
gcloud iam service-accounts create github-deployer \
  --display-name="GitHub Actions Deployer"

SA=github-deployer@meeting-assistant-473703.iam.gserviceaccount.com

gcloud projects add-iam-policy-binding meeting-assistant-473703 \
  --member="serviceAccount:$SA" --role="roles/run.admin"

gcloud projects add-iam-policy-binding meeting-assistant-473703 \
  --member="serviceAccount:$SA" --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding meeting-assistant-473703 \
  --member="serviceAccount:$SA" --role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding meeting-assistant-473703 \
  --member="serviceAccount:$SA" --role="roles/secretmanager.secretAccessor"
```

### 6b. Runtime service account (for Cloud Run)

```bash
gcloud iam service-accounts create lecturelink-runtime \
  --display-name="LectureLink Runtime"

RUNTIME_SA=lecturelink-runtime@meeting-assistant-473703.iam.gserviceaccount.com

gcloud projects add-iam-policy-binding meeting-assistant-473703 \
  --member="serviceAccount:$RUNTIME_SA" --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding meeting-assistant-473703 \
  --member="serviceAccount:$RUNTIME_SA" --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding meeting-assistant-473703 \
  --member="serviceAccount:$RUNTIME_SA" --role="roles/logging.logWriter"
```

---

## Step 7: Set Up Workload Identity Federation (GitHub → GCP)

This lets GitHub Actions authenticate to GCP without a service account key file.

### 7a. Get your project number

```bash
cccccccccccccccccc
```

**Save this as `PROJECT_NUMBER`.** 948583810015

### 7b. Create the identity pool and provider

```bash
gcloud iam workload-identity-pools create github-pool \
  --location=global \
  --display-name="GitHub Actions"

gcloud iam workload-identity-pools providers create-oidc github-provider \
  --location=global \
  --workload-identity-pool=github-pool \
  --display-name="GitHub" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository == 'thivian17/LectureLink-2.0'" \
  --issuer-uri="https://token.actions.githubusercontent.com"
```

### 7c. Allow your GitHub repo to impersonate the deploy SA

Replace `YOUR_GITHUB_ORG/YOUR_REPO_NAME` with your actual GitHub org/repo (e.g. `thivi/LectureLink-2.0`):

```bash
SA=github-deployer@meeting-assistant-473703.iam.gserviceaccount.com

gcloud iam service-accounts add-iam-policy-binding $SA \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/948583810015/locations/global/workloadIdentityPools/github-pool/attribute.repository/thivian17/LectureLink-2.0"
```

### 7d. Note the WIF provider resource name

You'll need this for GitHub secrets:
```
projects/948583810015/locations/global/workloadIdentityPools/github-pool/providers/github-provider
```

---

## Step 8: Configure DNS

In your domain registrar's DNS panel for `lecturelink.ca`, add:

| Type  | Name          | Value                    |
|-------|---------------|--------------------------|
| CNAME | `api`         | `ghs.googlehosted.com.`  |
| CNAME | `staging`     | `ghs.googlehosted.com.`  |
| CNAME | `staging-api` | `ghs.googlehosted.com.`  |

For the root domain (`lecturelink.ca`):
- If your registrar supports **ALIAS/ANAME** records: point `@` to `ghs.googlehosted.com.`
- If not: use `www.lecturelink.ca` (CNAME → `ghs.googlehosted.com.`) and set up a redirect from the apex domain

> DNS propagation can take up to 48 hours, but usually completes in 15-30 minutes.

---

## Step 9: First Manual Deployment

Do the first deployment manually to create the Cloud Run services. After this, CI/CD will handle future deploys.

### 9a. Set variables

```bash
PROJECT_ID=meeting-assistant-473703
REGISTRY=us-central1-docker.pkg.dev
REDIS_IP=10.139.150.251
RUNTIME_SA=lecturelink-runtime@${PROJECT_ID}.iam.gserviceaccount.com
```

### 9b. Authenticate Docker to Artifact Registry

```bash
gcloud auth configure-docker us-central1-docker.pkg.dev --quiet
```

### 9c. Build and push the API image

Run from the repo root:

```bash
docker build \
  -f packages/api/Dockerfile \
  -t ${REGISTRY}/${PROJECT_ID}/lecturelink/api:v1 \
  .

docker push ${REGISTRY}/${PROJECT_ID}/lecturelink/api:v1
```

### 9d. Build and push the Web image

Replace the Supabase values with your real ones:

```bash
docker build \
  -f packages/web/Dockerfile \
  -t ${REGISTRY}/${PROJECT_ID}/lecturelink/web:v1 \
  --build-arg NEXT_PUBLIC_SUPABASE_URL=https://ncypmtimgxfiumlkzrrz.supabase.co \
  --build-arg NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5jeXBtdGltZ3hmaXVtbGt6cnJ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA1MTgyNzAsImV4cCI6MjA4NjA5NDI3MH0.rXedsmhVpCB5ru3yryEiJYwogBdQzETNdUGtdg7ONkU \
  --build-arg NEXT_PUBLIC_API_URL=https://api.lecturelink.ca \
  .

docker push ${REGISTRY}/${PROJECT_ID}/lecturelink/web:v1
```

### 9e. Deploy the API service

```bash
gcloud run deploy lecturelink-api-prod \
  --image ${REGISTRY}/${PROJECT_ID}/lecturelink/api:v1 \
  --region us-central1 \
  --platform managed \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 1 \
  --max-instances 10 \
  --timeout 60s \
  --vpc-connector=lecturelink-connector \
  --service-account=$RUNTIME_SA \
  --set-secrets="SUPABASE_URL=SUPABASE_URL:latest,SUPABASE_ANON_KEY=SUPABASE_ANON_KEY:latest,SUPABASE_SERVICE_KEY=SUPABASE_SERVICE_ROLE_KEY:latest,GOOGLE_API_KEY=GEMINI_API_KEY:latest,INTERNAL_API_KEY=INTERNAL_API_KEY:latest" \
  --set-env-vars="ENVIRONMENT=production,GOOGLE_CLOUD_PROJECT=${PROJECT_ID},REDIS_URL=redis://${REDIS_IP}:6379,CORS_ORIGINS=https://lecturelink.ca" \
  --allow-unauthenticated
```

### 9f. Deploy the Worker service

Same Docker image as the API, but with a different start command:

```bash
gcloud run deploy lecturelink-worker-prod \
  --image ${REGISTRY}/${PROJECT_ID}/lecturelink/api:v1 \
  --region us-central1 \
  --platform managed \
  --command="python","-m","arq","lecturelink_api.worker.WorkerSettings" \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 1 \
  --max-instances 3 \
  --no-cpu-throttling \
  --vpc-connector=lecturelink-connector \
  --service-account=$RUNTIME_SA \
  --set-secrets="SUPABASE_URL=SUPABASE_URL:latest,SUPABASE_ANON_KEY=SUPABASE_ANON_KEY:latest,SUPABASE_SERVICE_KEY=SUPABASE_SERVICE_ROLE_KEY:latest,GOOGLE_API_KEY=GEMINI_API_KEY:latest" \
  --set-env-vars="ENVIRONMENT=production,GOOGLE_CLOUD_PROJECT=${PROJECT_ID},REDIS_URL=redis://${REDIS_IP}:6379" \
  --no-allow-unauthenticated
```

Key flags explained:
- `--no-cpu-throttling` — worker needs CPU even without HTTP requests (it polls Redis)
- `--min-instances 1` — always-on so background jobs run immediately
- `--no-allow-unauthenticated` — worker has no public endpoint

### 9g. Deploy the Web service

```bash
gcloud run deploy lecturelink-web-prod \
  --image ${REGISTRY}/${PROJECT_ID}/lecturelink/web:v1 \
  --region us-central1 \
  --platform managed \
  --memory 256Mi \
  --cpu 1 \
  --min-instances 1 \
  --max-instances 5 \
  --timeout 30s \
  --service-account=$RUNTIME_SA \
  --set-env-vars="NEXT_PUBLIC_API_URL=https://api.lecturelink.ca" \
  --allow-unauthenticated
```

### 9h. Verify the services are running

```bash
# Check the Cloud Run-assigned URLs first (before custom domains)
gcloud run services describe lecturelink-api-prod --region=us-central1 --format='value(status.url)'
gcloud run services describe lecturelink-web-prod --region=us-central1 --format='value(status.url)'

# Hit the API health check using the Cloud Run URL
API_URL=$(gcloud run services describe lecturelink-api-prod --region=us-central1 --format='value(status.url)')
curl "$API_URL/health"
# Expected: {"status":"ok","version":"0.1.0","environment":"production"}
```

---

## Step 10: Map Custom Domains

Now that the services exist, map your domains:

```bash
gcloud beta run domain-mappings create \
  --service=lecturelink-web-prod \
  --domain=lecturelink.ca \
  --region=us-central1

gcloud beta run domain-mappings create \
  --service=lecturelink-api-prod \
  --domain=api.lecturelink.ca \
  --region=us-central1
```

Google will auto-provision SSL certificates. Check status:

```bash
gcloud beta run domain-mappings list --region=us-central1
```

Certificate provisioning takes 15-30 minutes after DNS propagates. You can check progress:

```bash
gcloud beta run domain-mappings describe \
  --domain=lecturelink.ca \
  --region=us-central1
```

Once complete, verify:
```bash
curl https://api.lecturelink.ca/health
curl -s -o /dev/null -w '%{http_code}' https://lecturelink.ca
```

---

## Step 11: Configure Supabase for Production

In your Supabase dashboard (https://supabase.com/dashboard):

1. **Authentication → URL Configuration:**
   - Add `https://lecturelink.ca` to **Site URL**
   - Add `https://lecturelink.ca/**` to **Redirect URLs**

2. **Authentication → Providers:**
   - If using Google OAuth, update the authorized redirect URI to include your production domain

---

## Step 12: Set Up GitHub Actions Secrets

In your GitHub repo → **Settings → Secrets and variables → Actions**, add:

| Secret Name                       | Value                                                           |
|-----------------------------------|-----------------------------------------------------------------|
| `GCP_PROJECT_ID`                  | Your GCP project ID                                             |
| `WIF_PROVIDER`                    | `projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/providers/github-provider` |
| `WIF_SERVICE_ACCOUNT`             | `github-deployer@YOUR_PROJECT_ID.iam.gserviceaccount.com`       |
| `RUNTIME_SERVICE_ACCOUNT`         | `lecturelink-runtime@YOUR_PROJECT_ID.iam.gserviceaccount.com`   |
| `NEXT_PUBLIC_SUPABASE_URL`        | `https://YOUR_PROJECT.supabase.co`                              |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY`   | Your Supabase anon key                                          |
| `NEXT_PUBLIC_API_URL`             | `https://api.lecturelink.ca`                                    |
| `MEMORYSTORE_IP`                  | The Redis IP from Step 4                                        |

After this, every push to `main` will trigger the CI/CD pipeline in `.github/workflows/deploy.yml` which will: lint, test, build images, deploy to Cloud Run, smoke test, and shift traffic.

---

## Step 13: (Optional) Set Up Staging

If you want a staging environment at `staging.lecturelink.ca`:

1. Create staging Supabase secrets (if using a separate Supabase project):
   ```bash
   echo -n "https://YOUR_STAGING_PROJECT.supabase.co" | gcloud secrets create STAGING_SUPABASE_URL --data-file=-
   echo -n "STAGING_ANON_KEY" | gcloud secrets create STAGING_SUPABASE_ANON_KEY --data-file=-
   echo -n "STAGING_SERVICE_ROLE_KEY" | gcloud secrets create STAGING_SUPABASE_SERVICE_ROLE_KEY --data-file=-
   ```

2. Add staging GitHub secrets:
   | Secret Name                               | Value                                    |
   |-------------------------------------------|------------------------------------------|
   | `STAGING_NEXT_PUBLIC_SUPABASE_URL`        | Staging Supabase URL                     |
   | `STAGING_NEXT_PUBLIC_SUPABASE_ANON_KEY`   | Staging Supabase anon key                |
   | `STAGING_NEXT_PUBLIC_API_URL`             | `https://staging-api.lecturelink.ca`     |

3. Create a `develop` branch and push to it — this triggers `.github/workflows/deploy-staging.yml`

4. Map the staging domains:
   ```bash
   gcloud beta run domain-mappings create \
     --service=lecturelink-web-staging --domain=staging.lecturelink.ca --region=us-central1
   gcloud beta run domain-mappings create \
     --service=lecturelink-api-staging --domain=staging-api.lecturelink.ca --region=us-central1
   ```

---

## Verification Checklist

Run through these after deployment:

```bash
# API health
curl https://api.lecturelink.ca/health
# → {"status":"ok","version":"0.1.0","environment":"production"}

# API readiness (checks Supabase connection)
curl https://api.lecturelink.ca/health/ready
# → {"status":"ready","database":"ok"}

# Frontend loads
curl -s -o /dev/null -w '%{http_code}' https://lecturelink.ca
# → 200
```

Then test in the browser:
- [ ] https://lecturelink.ca loads the Next.js app
- [ ] SSL certificate shows (green padlock)
- [ ] Sign up / log in works via Supabase Auth
- [ ] Upload a syllabus — it should trigger background processing (worker)
- [ ] Quiz generation completes
- [ ] Push a commit to `main` — GitHub Actions deploys automatically

---

## Troubleshooting

**Cloud Run service won't start:**
```bash
gcloud run services logs read lecturelink-api-prod --region=us-central1 --limit=50
```

**Secret Manager errors at startup:**
- Check the runtime SA has `roles/secretmanager.secretAccessor`
- Check `GOOGLE_CLOUD_PROJECT` env var is set on the service

**Worker not processing jobs:**
- Verify Redis IP is correct: `gcloud redis instances describe lecturelink-redis --region=us-central1 --format='value(host)'`
- Check the worker service has the VPC connector attached
- Check worker logs: `gcloud run services logs read lecturelink-worker-prod --region=us-central1 --limit=50`

**CORS errors in browser:**
- The API's `CORS_ORIGINS` env var must include `https://lecturelink.ca`
- Check: `gcloud run services describe lecturelink-api-prod --region=us-central1 --format='yaml(spec.template.spec.containers[0].env)'`

**Domain mapping stuck at "pending":**
- Verify DNS records point to `ghs.googlehosted.com.`
- Check: `dig api.lecturelink.ca CNAME`
- SSL provisioning can take up to 24h in rare cases

---

## Cost Optimization Tips

- Set `--min-instances 0` on staging services (they'll cold-start in ~2-5s)
- Set `--min-instances 0` on production web/API if you're OK with occasional cold starts
- The worker **must** have `--min-instances 1` to poll Redis for jobs
- Memorystore Basic tier (1GB) is ~$35/mo — this is the fixed cost floor
- Estimated total: **~$125-165/mo** (GCP + Supabase Pro)
