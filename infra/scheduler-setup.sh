#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# LectureLink v2 — Cloud Scheduler Setup
#
# Creates a daily scheduler job that hits /internal/daily-refresh
# on the Cloud Run API service.  The job:
#   1. Refreshes study actions for all active users
#   2. Cleans up expired ADK sessions
#
# Prerequisites:
#   - gcloud CLI authenticated with a project that has:
#       * Cloud Scheduler API enabled
#       * Cloud Run API enabled
#       * Secret Manager API enabled
#   - Secret "INTERNAL_API_KEY" stored in Secret Manager
#   - A service account with roles/run.invoker on the API service
#
# Usage:
#   ./infra/scheduler-setup.sh [API_URL]
#
#   If API_URL is omitted the script reads it from the running
#   Cloud Run service.
# ============================================================

PROJECT="lecturelink-prod"
REGION="us-central1"
JOB_NAME="daily-study-refresh"
SCHEDULE="0 6 * * *"   # 06:00 UTC every day
SERVICE_ACCOUNT="cloud-scheduler-sa@${PROJECT}.iam.gserviceaccount.com"

# Resolve API URL --------------------------------------------------
if [ -n "${1:-}" ]; then
    API_URL="$1"
else
    API_URL=$(gcloud run services describe lecturelink-api \
        --region "${REGION}" \
        --format="value(status.url)" 2>/dev/null)
    if [ -z "${API_URL}" ]; then
        echo "ERROR: Could not resolve Cloud Run API URL."
        echo "Pass it as the first argument: ./infra/scheduler-setup.sh https://lecturelink-api-xxx.run.app"
        exit 1
    fi
fi

TARGET_URL="${API_URL}/internal/daily-refresh"

# Read the internal API key from Secret Manager --------------------
INTERNAL_API_KEY=$(gcloud secrets versions access latest \
    --secret=INTERNAL_API_KEY \
    --project="${PROJECT}" 2>/dev/null)

if [ -z "${INTERNAL_API_KEY}" ]; then
    echo "ERROR: Could not read INTERNAL_API_KEY from Secret Manager."
    exit 1
fi

echo "=== Cloud Scheduler Setup ==="
echo "  Job:     ${JOB_NAME}"
echo "  Target:  ${TARGET_URL}"
echo "  Schedule: ${SCHEDULE} (UTC)"
echo ""

# Create (or update) the scheduler job -----------------------------
# --http-method POST sends a POST request
# --headers passes the internal API key
# --oidc-service-account-email authenticates to Cloud Run
gcloud scheduler jobs create http "${JOB_NAME}" \
    --project="${PROJECT}" \
    --location="${REGION}" \
    --schedule="${SCHEDULE}" \
    --time-zone="UTC" \
    --http-method=POST \
    --uri="${TARGET_URL}" \
    --headers="X-Internal-API-Key=${INTERNAL_API_KEY},Content-Type=application/json" \
    --oidc-service-account-email="${SERVICE_ACCOUNT}" \
    --oidc-token-audience="${API_URL}" \
    --attempt-deadline="120s" \
    --description="Daily refresh: regenerate study actions and clean up expired sessions" \
    2>/dev/null \
|| gcloud scheduler jobs update http "${JOB_NAME}" \
    --project="${PROJECT}" \
    --location="${REGION}" \
    --schedule="${SCHEDULE}" \
    --time-zone="UTC" \
    --http-method=POST \
    --uri="${TARGET_URL}" \
    --headers="X-Internal-API-Key=${INTERNAL_API_KEY},Content-Type=application/json" \
    --oidc-service-account-email="${SERVICE_ACCOUNT}" \
    --oidc-token-audience="${API_URL}" \
    --attempt-deadline="120s" \
    --description="Daily refresh: regenerate study actions and clean up expired sessions"

echo ""
echo "=== Done ==="
echo "  Job '${JOB_NAME}' configured to POST ${TARGET_URL} daily at ${SCHEDULE}"
echo ""
echo "  To trigger manually:"
echo "    gcloud scheduler jobs run ${JOB_NAME} --location=${REGION}"
