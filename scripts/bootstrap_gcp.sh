#!/usr/bin/env bash
# One-time GCP setup for the monthly Dagster schedule.
#
# Creates the wake shared secret, grants secret access to the Cloud Run and
# Cloud Build service accounts, and installs a log-based failure alert with an
# email notification channel.
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
ALERT_EMAIL="${ALERT_EMAIL:-}"

if [[ -z "$PROJECT_ID" ]]; then
  echo "PROJECT_ID is required (set GCP_PROJECT_ID in .env or run gcloud config set project <id>)" >&2
  exit 1
fi

if [[ -z "$ALERT_EMAIL" ]]; then
  echo "ALERT_EMAIL is required (set ALERT_EMAIL in .env or pass ALERT_EMAIL=you@example.com $0)" >&2
  exit 1
fi

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
RUNTIME_SA="${RUNTIME_SA:-${PROJECT_NUMBER}-compute@developer.gserviceaccount.com}"
CLOUD_BUILD_SA="${CLOUD_BUILD_SA:-}"

echo "[bootstrap] project=$PROJECT_ID region=$REGION service=$SERVICE"
echo "[bootstrap] runtime service account=$RUNTIME_SA"

gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  cloudscheduler.googleapis.com \
  secretmanager.googleapis.com \
  monitoring.googleapis.com \
  logging.googleapis.com \
  --project="$PROJECT_ID"

# Projects created before April 2024 use the Compute Engine default service
# account for Cloud Build; newer projects use the Cloud Build service account.
# Grant both unless the caller explicitly overrides the build identity, so the
# token mount works either way (including when iam.serviceAccounts.get is
# denied and the account cannot be probed directly).
BUILD_SAS=("$RUNTIME_SA")
if [[ -n "$CLOUD_BUILD_SA" ]]; then
  BUILD_SAS=("$CLOUD_BUILD_SA")
else
  BUILD_SAS+=("${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com")
fi
echo "[bootstrap] Cloud Build candidate service account(s)=${BUILD_SAS[*]}"

# The wake secret authenticates Cloud Scheduler's POST /wake request. Do not
# rotate an existing secret here: the scheduler header is refreshed by
# deploy_dagster.sh.
if gcloud secrets describe wake-shared-secret --project="$PROJECT_ID" >/dev/null 2>&1; then
  echo "[bootstrap] wake-shared-secret already exists; leaving it unchanged"
else
  openssl rand -hex 32 | tr -d '\n' | gcloud secrets create wake-shared-secret \
    --data-file=- \
    --replication-policy=automatic \
    --project="$PROJECT_ID"
  echo "[bootstrap] created wake-shared-secret"
fi

for secret in \
  motherduck-token \
  r2-account-id \
  r2-access-key-id \
  r2-secret-access-key \
  wake-shared-secret
do
  if ! gcloud secrets describe "$secret" --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "[bootstrap] WARNING: secret $secret does not exist; create it before deploying" >&2
    continue
  fi

  gcloud secrets add-iam-policy-binding "$secret" \
    --member="serviceAccount:${RUNTIME_SA}" \
    --role="roles/secretmanager.secretAccessor" \
    --project="$PROJECT_ID" \
    --quiet >/dev/null
  echo "[bootstrap] granted runtime access to $secret"
done

# The Docker build mounts motherduck-token as a BuildKit secret. Grant the
# possible build identities; one of them is the identity Cloud Build uses.
if gcloud secrets describe motherduck-token --project="$PROJECT_ID" >/dev/null 2>&1; then
  for build_sa in "${BUILD_SAS[@]}"; do
    if gcloud secrets add-iam-policy-binding motherduck-token \
      --member="serviceAccount:${build_sa}" \
      --role="roles/secretmanager.secretAccessor" \
      --project="$PROJECT_ID" \
      --quiet >/dev/null; then
      echo "[bootstrap] granted Cloud Build access to motherduck-token for $build_sa"
    else
      echo "[bootstrap] WARNING: could not grant $build_sa access to motherduck-token" >&2
    fi
  done
fi

ensure_log_metric() {
  local name="$1"
  local filter="$2"

  if gcloud logging metrics describe "$name" --project="$PROJECT_ID" >/dev/null 2>&1; then
    gcloud logging metrics update "$name" \
      --project="$PROJECT_ID" \
      --description="Dagster monthly comics failure signal" \
      --log-filter="$filter" >/dev/null
  else
    gcloud logging metrics create "$name" \
      --project="$PROJECT_ID" \
      --description="Dagster monthly comics failure signal" \
      --log-filter="$filter" >/dev/null
  fi
  echo "[bootstrap] upserted log metric $name"
}

ensure_log_metric dagster_wake_failures \
  "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${SERVICE}\" AND jsonPayload.event=\"wake_run_failed\""
ensure_log_metric dagster_scheduler_failures \
  "resource.type=\"cloud_scheduler_job\" AND resource.labels.job_id=(\"${JOB}\" OR \"${CHECK_JOB}\") AND severity>=ERROR"

CHANNEL_NAME="$(gcloud beta monitoring channels list \
  --project="$PROJECT_ID" \
  --filter="type=\"email\" AND labels.email_address=\"${ALERT_EMAIL}\"" \
  --format='value(name)' | head -n 1)"
if [[ -z "$CHANNEL_NAME" ]]; then
  CHANNEL_NAME="$(gcloud beta monitoring channels create \
    --project="$PROJECT_ID" \
    --type=email \
    --display-name="Dagster alerts" \
    --channel-labels=email_address="$ALERT_EMAIL" \
    --format='value(name)')"
  echo "[bootstrap] created email notification channel for $ALERT_EMAIL"
else
  echo "[bootstrap] reusing notification channel $CHANNEL_NAME"
fi

POLICY_FILE="$(mktemp)"
trap 'rm -f "$POLICY_FILE"' EXIT

# The Monitoring API allows only one conditionMatchedLog per alert policy, so
# upsert one single-condition policy for each failure source.
ensure_alert_policy() {
  local display_name="$1"
  local condition_name="$2"
  local filter="$3"
  python3 - "$display_name" "$condition_name" "$filter" "$CHANNEL_NAME" > "$POLICY_FILE" <<'PY'
import json
import sys

display_name, condition_name, log_filter, channel = sys.argv[1:5]
print(json.dumps({
    "displayName": display_name,
    "documentation": {
        "mime_type": "text/markdown",
        "content": (
            "Runbook: check Cloud Run logs for wake_run_failed or "
            "wake_status_failed, then inspect the Dagster run and R2 state "
            "in the Cloud Run console. The /wake/status check runs at 12:00 "
            "UTC on the first of each month."
        ),
    },
    "combiner": "OR",
    "enabled": True,
    "alertStrategy": {"notificationRateLimit": {"period": "300s"}},
    "conditions": [{
        "displayName": condition_name,
        "conditionMatchedLog": {"filter": log_filter},
    }],
    "notificationChannels": [channel],
}, indent=2))
PY

  local policy_name
  policy_name="$(gcloud alpha monitoring policies list \
    --project="$PROJECT_ID" \
    --filter="display_name=\"${display_name}\"" \
    --format='value(name)' | head -n 1)"

  if [[ -n "$policy_name" ]]; then
    gcloud alpha monitoring policies update "$policy_name" \
      --project="$PROJECT_ID" \
      --policy-from-file="$POLICY_FILE"
    echo "[bootstrap] updated alert policy $policy_name"
  else
    gcloud alpha monitoring policies create \
      --project="$PROJECT_ID" \
      --policy-from-file="$POLICY_FILE"
    echo "[bootstrap] created alert policy ${display_name}"
  fi
}

ensure_alert_policy \
  "Dagster monthly comics wake failed" \
  "Wake run failed" \
  "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${SERVICE}\" AND jsonPayload.event=\"wake_run_failed\""

ensure_alert_policy \
  "Dagster monthly comics scheduler failed" \
  "Cloud Scheduler job failed" \
  "resource.type=\"cloud_scheduler_job\" AND resource.labels.job_id=(\"${JOB}\" OR \"${CHECK_JOB}\") AND severity>=ERROR"

echo "[bootstrap] done. Run scripts/deploy_dagster.sh next."
