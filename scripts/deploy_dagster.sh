#!/usr/bin/env bash
# Build and deploy the Dagster Cloud Run service, then upsert the two Cloud
# Scheduler jobs:
#   dagster-comics-monthly       08:00 UTC on the 1st -> POST /wake
#   dagster-comics-monthly-check 12:00 UTC on the 1st -> GET  /wake/status
#
# Run scripts/bootstrap_gcp.sh once first.
set -euo pipefail

# Auto-load .env if present in current directory or repo root
if [[ -f .env ]]; then
  set -a && source .env && set +a
elif [[ -f "$(dirname "$0")/../.env" ]]; then
  set -a && source "$(dirname "$0")/../.env" && set +a
fi

PROJECT_ID="${PROJECT_ID:-${GCP_PROJECT_ID:-${BQ_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}}}"
REGION="${REGION:-${GCP_REGION:-northamerica-northeast1}}"
SERVICE="${SERVICE:-analytics-dagster}"
JOB="${JOB:-dagster-comics-monthly}"
CHECK_JOB="${CHECK_JOB:-dagster-comics-monthly-check}"
BUCKET="${DAGSTER_R2_BUCKET:-xkcd-ingest}"
PREFIX="${DAGSTER_R2_PREFIX:-dagster_home}"
CRON_SCHEDULE="${CRON_SCHEDULE:-0 8 1 * *}"
CHECK_CRON_SCHEDULE="${CHECK_CRON_SCHEDULE:-0 12 1 * *}"
TAG="${TAG:-$(git rev-parse --short HEAD)}"

if [[ -z "$PROJECT_ID" ]]; then
  echo "PROJECT_ID is required (set GCP_PROJECT_ID in .env or run gcloud config set project <id>)" >&2
  exit 1
fi

IMAGE="gcr.io/${PROJECT_ID}/${SERVICE}:${TAG}"

echo "[deploy] building ${IMAGE}"
gcloud builds submit --quiet \
  --project="$PROJECT_ID" \
  --config=cloudbuild.yaml \
  --ignore-file=.dockerignore \
  --substitutions="_TAG=${TAG},_SERVICE=${SERVICE}" \
  .

WAKE_SECRET="$(gcloud secrets versions access latest \
  --secret=wake-shared-secret \
  --project="$PROJECT_ID")"

if [[ -z "$WAKE_SECRET" ]]; then
  echo "wake-shared-secret is empty; run scripts/bootstrap_gcp.sh" >&2
  exit 1
fi

echo "[deploy] deploying Cloud Run service ${SERVICE}"
gcloud run deploy "$SERVICE" --quiet \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --image="$IMAGE" \
  --platform=managed \
  --allow-unauthenticated \
  --min-instances=0 \
  --max-instances=1 \
  --memory=2Gi \
  --cpu=1 \
  --cpu-boost \
  --no-cpu-throttling \
  --timeout=3600 \
  --port=8080 \
  --concurrency=200 \
  --set-env-vars="DAGSTER_HOME=/tmp/dagster_home,DAGSTER_R2_BUCKET=${BUCKET},DAGSTER_R2_PREFIX=${PREFIX},AWS_REGION=auto,MOTHERDUCK_DATABASE=data_warehouse_demo,WAKE_TIMEOUT_SECONDS=1500,WAKE_POLL_INTERVAL_SECONDS=10,DAGSTER_GRAPHQL_URL=http://127.0.0.1:3000/graphql,DAGSTER_INGESTION_JOB=comics_ingestion_job,DAGSTER_TRANSFORMATION_JOB=comics_transformation_job" \
  --set-secrets="MOTHERDUCK_TOKEN=motherduck-token:latest,R2_ACCOUNT_ID=r2-account-id:latest,R2_ACCESS_KEY_ID=r2-access-key-id:latest,R2_SECRET_ACCESS_KEY=r2-secret-access-key:latest,WAKE_SHARED_SECRET=wake-shared-secret:latest"

SERVICE_URL="$(gcloud run services describe "$SERVICE" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --format='value(status.url)')"

echo "[deploy] service URL: ${SERVICE_URL}"

# Wait for the cold start and the build-time dbt docs to be served.
READY=0
for _ in $(seq 1 30); do
  if curl -fsS --max-time 60 "${SERVICE_URL}/server_info" >/dev/null; then
    READY=1
    break
  fi
  sleep 5
done

if [[ "$READY" -ne 1 ]]; then
  echo "[deploy] ERROR: ${SERVICE_URL}/server_info did not become ready" >&2
  exit 1
fi

curl -fsSI --max-time 60 "${SERVICE_URL}/dbt-docs/" >/dev/null
echo "[deploy] server and dbt docs are responding"

upsert_scheduler_job() {
  local name="$1"
  local schedule="$2"
  local method="$3"
  local path="$4"
  local deadline="$5"

  if gcloud scheduler jobs describe "$name" \
    --project="$PROJECT_ID" \
    --location="$REGION" >/dev/null 2>&1; then
    gcloud scheduler jobs update http "$name" \
      --project="$PROJECT_ID" \
      --location="$REGION" \
      --schedule="$schedule" \
      --time-zone="Etc/UTC" \
      --uri="${SERVICE_URL}${path}" \
      --http-method="$method" \
      --update-headers="X-Wake-Secret=${WAKE_SECRET}" \
      --attempt-deadline="$deadline" \
      --max-retry-attempts=3 \
      --min-backoff=60s \
      --max-backoff=300s
  else
    gcloud scheduler jobs create http "$name" \
      --project="$PROJECT_ID" \
      --location="$REGION" \
      --schedule="$schedule" \
      --time-zone="Etc/UTC" \
      --uri="${SERVICE_URL}${path}" \
      --http-method="$method" \
      --headers="X-Wake-Secret=${WAKE_SECRET}" \
      --attempt-deadline="$deadline" \
      --max-retry-attempts=3 \
      --min-backoff=60s \
      --max-backoff=300s
  fi
}

echo "[deploy] upserting scheduler jobs"
upsert_scheduler_job "$JOB" "$CRON_SCHEDULE" "POST" "/wake" "1800s"
upsert_scheduler_job "$CHECK_JOB" "$CHECK_CRON_SCHEDULE" "GET" "/wake/status" "300s"

echo "[deploy] done"
gcloud scheduler jobs describe "$JOB" --project="$PROJECT_ID" --location="$REGION" --format='value(name,schedule,timeZone,httpTarget.uri)'
gcloud scheduler jobs describe "$CHECK_JOB" --project="$PROJECT_ID" --location="$REGION" --format='value(name,schedule,timeZone,httpTarget.uri)'
