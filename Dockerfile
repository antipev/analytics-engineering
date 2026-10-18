# Cloud Run prototype: Dagster webserver + daemon and dbt docs for analytics-engineering.
# Build context = repo root (the dbt project lives outside ingestion/).
FROM python:3.12-slim

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
    nginx \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# requirements.txt is generated from ingestion/orchestration_dagster/uv.lock:
#   uv export --all-groups --no-hashes --no-emit-project -o requirements.txt
COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# Project code.
COPY ingestion/orchestration_dagster /app/ingestion/orchestration_dagster
COPY transformation_dbt /app/transformation_dbt

# dbt packages are installed at build time; docs are generated at startup because
# they need the MotherDuck token and live catalog metadata.
RUN cd /app/transformation_dbt/domain_data_products \
    && dbt deps \
    && mkdir -p /tmp/dagster_home /app/transformation_dbt/domain_data_products/target

# nginx + supervisor + startup scripts.
COPY docker/ /app/docker/
RUN chmod +x /app/docker/entrypoint.sh /app/docker/start-nginx.sh

WORKDIR /app/ingestion/orchestration_dagster

EXPOSE 8080
ENTRYPOINT ["/app/docker/entrypoint.sh"]
