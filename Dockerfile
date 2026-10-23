# syntax=docker/dockerfile:1.7
# Cloud Run prototype: Dagster webserver + daemon and dbt docs for analytics-engineering.
# Build context = repo root (the dbt project lives outside ingestion/).
FROM python:3.12-slim

ARG LITESTREAM_VERSION=0.5.14

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DAGSTER_HOME=/tmp/dagster_home \
    DBT_TARGET=motherduck_dev \
    DBT_PROFILES_DIR=/app/transformation_dbt/domain_data_products \
    PYTHONPATH=/app/ingestion/orchestration_dagster/src \
    PORT=8080

WORKDIR /app

# nginx serves the public Cloud Run port and proxies Dagster on 127.0.0.1:3000.
# supervisor keeps the Dagster dev server and nginx alive together.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    nginx \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Litestream continuously replicates Dagster's SQLite state to Cloudflare R2.
RUN curl -fsSL \
      "https://github.com/benbjohnson/litestream/releases/download/v${LITESTREAM_VERSION}/litestream-${LITESTREAM_VERSION}-linux-x86_64.deb" \
      -o /tmp/litestream.deb \
    && dpkg -i /tmp/litestream.deb \
    && rm /tmp/litestream.deb

# requirements.txt is generated from ingestion/orchestration_dagster/uv.lock:
#   uv export --all-groups --no-hashes --no-emit-project -o requirements.txt
COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# Project code.
COPY ingestion/orchestration_dagster /app/ingestion/orchestration_dagster
COPY transformation_dbt /app/transformation_dbt

# profiles.yml is gitignored (it can carry credentials), so a clean checkout has
# none — and a laptop build silently bakes in the local one. Fall back to the
# tracked example, whose outputs are all env-driven; without this, `dbt docs
# generate` below fails on any build that did not start from a warm worktree.
RUN cd /app/transformation_dbt/domain_data_products \
    && { [ -f profiles.yml ] || cp profiles.example.yml profiles.yml; }

# dbt packages and docs are generated at image-build time. The MotherDuck token
# is mounted as a BuildKit secret and is never stored in an image layer. When no
# token is supplied, build an empty-catalog docs site from a temporary DuckDB
# target so local builds and deploys still work without live catalog metadata.
RUN cd /app/transformation_dbt/domain_data_products \
    && dbt deps \
    && mkdir -p /tmp/dagster_home /app/transformation_dbt/domain_data_products/target

RUN --mount=type=secret,id=motherduck_token,required=false \
    cd /app/transformation_dbt/domain_data_products && \
    if [ -s /run/secrets/motherduck_token ]; then \
        echo "[build] Generating dbt docs against MotherDuck"; \
        if ! MOTHERDUCK_TOKEN="$(cat /run/secrets/motherduck_token)" \
             dbt docs generate \
                 --profiles-dir "$DBT_PROFILES_DIR" \
                 --target motherduck_dev; then \
            echo "[build] WARNING: MotherDuck docs failed; using empty catalog"; \
            XKCD_DUCKDB_PATH=/tmp/dbt_docs.duckdb dbt docs generate \
                --profiles-dir "$DBT_PROFILES_DIR" \
                --target duckdb_dev \
                --empty-catalog; \
        fi; \
    else \
        echo "[build] No MotherDuck token; generating empty-catalog dbt docs"; \
        XKCD_DUCKDB_PATH=/tmp/dbt_docs.duckdb dbt docs generate \
            --profiles-dir "$DBT_PROFILES_DIR" \
            --target duckdb_dev \
            --empty-catalog; \
    fi

# nginx + supervisor + startup scripts.
COPY docker/ /app/docker/
RUN chmod +x /app/docker/entrypoint.sh /app/docker/start-nginx.sh

WORKDIR /app/ingestion/orchestration_dagster

EXPOSE 8080
ENTRYPOINT ["/app/docker/entrypoint.sh"]
