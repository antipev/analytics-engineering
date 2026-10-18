#!/usr/bin/env bash
set -euo pipefail

export PORT="${PORT:-8080}"
export DBT_PROFILES_DIR="${DBT_PROFILES_DIR:-/app/transformation_dbt/domain_data_products}"
export DBT_TARGET="${DBT_TARGET:-motherduck_dev}"
export DAGSTER_HOME="${DAGSTER_HOME:-/tmp/dagster_home}"
mkdir -p "$DAGSTER_HOME"

DBT_PROJECT_DIR=/app/transformation_dbt/domain_data_products
mkdir -p "$DBT_PROJECT_DIR/target"

run_local_docs_fallback() {
    echo "[entrypoint] Generating docs against a temporary local DuckDB target"
    (cd "$DBT_PROJECT_DIR" && \
        XKCD_DUCKDB_PATH="${TMPDIR:-/tmp}/dbt_docs.duckdb" \
        timeout 60 dbt docs generate \
            --profiles-dir "$DBT_PROFILES_DIR" \
            --target duckdb_dev \
            --empty-catalog) || \
        echo "[entrypoint] WARNING: dbt docs fallback failed; /dbt-docs will be unavailable"
}

# Generate dbt docs at startup: catalog metadata requires a live MotherDuck
# connection, so it cannot be generated at image-build time. If the catalog
# query fails, generate a docs site from a temporary empty local DuckDB target
# so the docs are still readable. Dagster must start even if docs generation
# fails.
if [ -n "${MOTHERDUCK_TOKEN:-}" ]; then
    echo "[entrypoint] Generating dbt docs against target=${DBT_TARGET}"
    if ! (cd "$DBT_PROJECT_DIR" && timeout 120 dbt docs generate --profiles-dir "$DBT_PROFILES_DIR" --target "$DBT_TARGET"); then
        echo "[entrypoint] WARNING: dbt docs generation failed"
        run_local_docs_fallback
    fi
else
    echo "[entrypoint] WARNING: MOTHERDUCK_TOKEN is not set"
    run_local_docs_fallback
fi

# Render the single nginx listen port from Cloud Run's $PORT.
sed "s/__PORT__/${PORT}/g" /app/docker/nginx.conf.template > /tmp/nginx.conf

exec /usr/bin/supervisord -c /app/docker/supervisord.conf
