#!/usr/bin/env bash
set -euo pipefail

export PORT="${PORT:-8080}"
export DBT_PROFILES_DIR="${DBT_PROFILES_DIR:-/app/transformation_dbt/domain_data_products}"
export DBT_TARGET="${DBT_TARGET:-motherduck_dev}"
export DAGSTER_HOME="${DAGSTER_HOME:-/tmp/dagster_home}"
export AWS_ACCESS_KEY_ID="${R2_ACCESS_KEY_ID:-}"
export AWS_SECRET_ACCESS_KEY="${R2_SECRET_ACCESS_KEY:-}"
export AWS_REGION="${AWS_REGION:-auto}"

mkdir -p "$DAGSTER_HOME/history/runs" "$DAGSTER_HOME/schedules"

# Restore Dagster's SQLite state from R2 before the daemon/webserver start.
# dbt docs are already built into the image; no docs generation happens here.
python /app/docker/restore_dagster_state.py

# The restore script resolves which replica epoch is live and records it here.
# Litestream must replicate into that same epoch, or a self-heal would leave the
# new generation somewhere the next boot does not read.
DAGSTER_REPLICA_EPOCH="$(cat "${DAGSTER_REPLICA_EPOCH_FILE:-/tmp/dagster_replica_epoch}" 2>/dev/null || true)"
export DAGSTER_REPLICA_EPOCH="${DAGSTER_REPLICA_EPOCH:-g0}"
echo "[entrypoint] Litestream replicates to ${DAGSTER_R2_PREFIX:-dagster_home}/${DAGSTER_REPLICA_EPOCH}"

# A restored schedule may still be RUNNING from an older deployment. The code
# default only applies to schedules without stored state, so force STOPPED
# before the daemon can tick or race the /wake endpoint.
python /app/docker/ensure_schedule_stopped.py

# Render the single nginx listen port from Cloud Run's $PORT.
sed "s/__PORT__/${PORT}/g" /app/docker/nginx.conf.template > /tmp/nginx.conf

exec /usr/bin/supervisord -c /app/docker/supervisord.conf
