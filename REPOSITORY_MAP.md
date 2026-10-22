# Repository map

This map inventories the repository's tracked files and the local-only or generated paths, so the repository can be audited file by file. Exact paths are relative to the repository root. Generated artifacts and local secrets are listed separately at the end and are not part of the deployed system. Return to [README.md](README.md).

## Root, build, and deployment

- **`README.md`** — Project overview, component diagram, architecture, run instructions, and validation evidence.
- **`REPOSITORY_MAP.md`** — File-by-file inventory of the repository, split out of `README.md`.
- **`Dockerfile`** — Builds the Python 3.12 runtime image: installs nginx, supervisor, Litestream, and pinned Python dependencies; copies code; runs `dbt deps`; generates dbt docs at build time with an optional BuildKit secret.
- **`.dockerignore`** — Keeps secrets, virtualenvs, generated dbt/Dagster state, notebooks, and `DOCUMENTATION/` out of the image build context.
- **`cloudbuild.yaml`** — Cloud Build pipeline: enables BuildKit, pulls `motherduck-token` from Secret Manager, builds the `linux/amd64` image, and pushes it to Container Registry.
- **`requirements.txt`** — Fully resolved, pinned Python dependency set exported from `ingestion/orchestration_dagster/uv.lock`; installed by the Docker image.
- **`.env.example`** — Template for local and deployment variables: GCP project/region, alert email, R2, MotherDuck, dbt target, and monthly scheduler settings.
- **`.gitignore`** — Excludes local secrets, virtualenvs, databases, logs, and generated artifacts from version control.
- **`scripts/bootstrap_gcp.sh`** — One-time GCP bootstrap: enables APIs, grants secret access to runtime/build service accounts, creates `wake-shared-secret`, upserts two log-based metrics, an email notification channel, and two alert policies.
- **`scripts/deploy_dagster.sh`** — Release command: builds with `cloudbuild.yaml`, deploys the Cloud Run service with scale-to-zero settings and secrets, waits for readiness, verifies dbt docs, and creates or updates both Cloud Scheduler jobs.
- **`PICTURES/Analytic Module Deployment Benefits.png`** — Illustration of the business value of analytic module deployment.
- **`PICTURES/Digital Transformation.png`** — Illustration of digital transformation versus digitalization.
- **`PICTURES/Dagster Lineage.png`** — Screenshot evidence of global Dagster asset lineage across both domains.
- **`PICTURES/Comics.png`** — Screenshot of xkcd.com, the source site for the comics domain.
- **`PICTURES/JaffleShop.png`** — Screenshot of the dbt Labs Jaffle Shop repository, the source of the cafe domain seeds.
- **`PICTURES/DBT Documentation.png`** — Screenshot evidence of generated dbt docs, source metadata, and Dagster asset links.
- **`PICTURES/Credible.png`** — Screenshot of the versioned `comics` package in Credible.
- **`PICTURES/Malloy Publisher.png`** — Screenshot of the `comics_explore` query and results in Malloy Publisher.
- **`PICTURES/Mother Duck.png`** — Screenshot of the MotherDuck database and schemas used by the semantic layer.

## Container runtime (`docker/`)

- **`docker/entrypoint.sh`** — Cold-start sequence: sets `DAGSTER_HOME`/dbt/R2 environment, creates state directories, restores SQLite from R2, forces the monthly schedule stopped, renders nginx for Cloud Run's `$PORT`, then starts supervisord.
- **`docker/restore_dagster_state.py`** — Lists Litestream replica prefixes in R2 and restores `runs.db`, `event_log.db`, `schedules.db`, and every per-run event-log database in parallel; exits non-zero on failure so an empty state does not start silently.
- **`docker/ensure_schedule_stopped.py`** — Reads restored Dagster schedule state and forces `comics_ingestion_schedule` to `STOPPED`, preventing the daemon from racing the `/wake` endpoint.
- **`docker/litestream.yml`** — Litestream configuration: continuously replicates `$DAGSTER_HOME/history/*.db` and `$DAGSTER_HOME/schedules/*.db` to Cloudflare R2 with a 1-second sync interval.
- **`docker/supervisord.conf`** — Process manager inside the container: starts Litestream, Dagster (`dg dev` on port 3000), the wake API (port 3001), and nginx, with restart policies and stdout/stderr logging.
- **`docker/wake_app.py`** — Starlette/uvicorn service for `/wake`, `/wake/status`, and `/healthz`; validates the shared secret, launches ingestion idempotently, waits for the sensor-triggered transformation, and reports the monthly run status.
- **`docker/nginx.conf.template`** — nginx template rendered with Cloud Run's `$PORT`; routes `/dbt-docs/` to static files, `/wake` and `/wake/status` to the wake API with long timeouts, and everything else to Dagster with WebSocket support.
- **`docker/start-nginx.sh`** — Waits until Dagster's `/server_info` responds, then starts nginx in the foreground under supervisord.

## Dagster orchestration (`ingestion/orchestration_dagster/`)

- **`ingestion/orchestration_dagster/pyproject.toml`** — Python project metadata and dependencies: Dagster, dagster-dbt, dbt-duckdb, DuckDB, pandas, boto3, and python-dotenv; also configures the Dagster project root.
- **`ingestion/orchestration_dagster/uv.lock`** — Locked dependency graph used by `uv sync` for local development.
- **`ingestion/orchestration_dagster/README.md`** — Local Dagster scaffold README (untracked); the repository-level README is authoritative.
- **`ingestion/orchestration_dagster/.gitignore`** — Excludes the local virtualenv, Dagster state, and caches from version control.
- **`ingestion/orchestration_dagster/.dg/telemetry.yaml`** — Dagster CLI project telemetry metadata; not used at runtime.
- **`ingestion/orchestration_dagster/src/orchestration_dagster/__init__.py`** — Marks the Python package.
- **`ingestion/orchestration_dagster/src/orchestration_dagster/definitions.py`** — Dagster entry point: loads all definitions from the `defs/` folder using `load_from_defs_folder`.
- **`ingestion/orchestration_dagster/src/orchestration_dagster/defs/__init__.py`** — Marks the definitions package.
- **`ingestion/orchestration_dagster/src/orchestration_dagster/defs/pipeline_config.py`** — Single source of truth for comic asset keys, the six Jaffle seed names, and the asset-key selection per domain.
- **`ingestion/orchestration_dagster/src/orchestration_dagster/defs/schedules.py`** — Declares `comics_ingestion_schedule` for `0 8 1 * *`; `default_status=STOPPED` so Cloud Scheduler remains the only monthly trigger.
- **`ingestion/orchestration_dagster/src/orchestration_dagster/defs/sensors.py`** — Two asset sensors: `raw_comics_v2` triggers `comics_transformation_job`; `raw_supplies` triggers `jaffle_shop_transformation_job`.
- **`ingestion/orchestration_dagster/src/orchestration_dagster/defs/step_0_ingestion_comics.py`** — XKCD ingestion asset `raw_comics`: finds the latest comic, compares it with R2 contents, downloads missing JSON files in parallel (skipping #404), and supports `full_refresh`.
- **`ingestion/orchestration_dagster/src/orchestration_dagster/defs/step_1_ingestion_comics.py`** — XKCD loading asset `raw_comics_v2`: reads missing JSON files from R2, validates them against a schema config, and inserts them into MotherDuck in batches.
- **`ingestion/orchestration_dagster/src/orchestration_dagster/defs/step_1_ingestion_jaffle_shop.py`** — Defines six chained dbt seed assets (`raw_customers` through `raw_supplies`) with a runtime `full_refresh` option.
- **`ingestion/orchestration_dagster/src/orchestration_dagster/defs/step_2_transformation_dbt.py`** — Discovers domain folders under `models/`, then creates `<domain>_ingestion_job` and `<domain>_transformation_job` asset jobs.
- **`ingestion/orchestration_dagster/src/orchestration_dagster/defs/transformation_dbt/component.py`** — `FullRefreshDbtProjectComponent`: subclasses `DbtProjectComponent` to expose a runtime `full_refresh` toggle that adds `--full-refresh` to dbt commands.
- **`ingestion/orchestration_dagster/src/orchestration_dagster/defs/transformation_dbt/defs.yaml`** — Registers the custom dbt component, points at the dbt project, excludes seed resources from the component, and assigns asset groups from the dbt FQN.
- **`ingestion/orchestration_dagster/src/orchestration_dagster/defs/transformation_dbt/template_vars.py`** — Locates the dbt project, resolves the default target (`motherduck_dev`), and provides the FQN-to-group helper used by the dbt component and job factory.
- **`ingestion/orchestration_dagster/src/orchestration_dagster/defs/data/schema_config_v1.json`** — Legacy XKCD raw schema (11 columns, no `extra_parts`); retained for schema-version compatibility.
- **`ingestion/orchestration_dagster/src/orchestration_dagster/defs/data/schema_config_v2.json`** — Active XKCD raw schema (12 columns, including `extra_parts`) used to validate records before loading into `raw_comics_v2`.
- **`ingestion/orchestration_dagster/src/orchestration_dagster/defs/data/test_ingestion.ipynb`** — Local scratch notebook for developing and debugging ingestion logic; untracked, not deployed.
- **`ingestion/orchestration_dagster/src/orchestration_dagster/defs/data/test_dbt.ipynb`** — Local scratch notebook for querying dbt/MotherDuck outputs; untracked, not deployed.
- **`ingestion/orchestration_dagster/src/orchestration_dagster/defs/data/test_query.sql`** — Local ad hoc MotherDuck inspection and cleanup queries; untracked, not executed by a job.
- **`ingestion/orchestration_dagster/tests/__init__.py`** — Marks the test package; no test modules are currently implemented.

## dbt project (`transformation_dbt/domain_data_products/`)

### Project configuration

- **`transformation_dbt/domain_data_products/dbt_project.yml`** — dbt project definition: name, profile, model/macro/seed paths, `ingest_jaffle_shop` seed schema, `staging`/`intermediate`/`marts` model folders, and strict static analysis.
- **`transformation_dbt/domain_data_products/profiles.yml`** — Local, gitignored connection targets: `motherduck_dev` (default cloud DWH), `duckdb_dev` (local file), and a BigQuery `dev` target.
- **`transformation_dbt/domain_data_products/packages.yml`** — Declares the `dbt-labs/dbt_utils` dependency.
- **`transformation_dbt/domain_data_products/package-lock.yml`** — Locks the resolved dbt package versions installed by `dbt deps`.
- **`transformation_dbt/domain_data_products/README.md`** — Local upstream Jaffle Shop scaffold README (untracked); the repository-level README is authoritative.
- **`transformation_dbt/domain_data_products/.gitignore`** — Excludes dbt build artifacts, packages, logs, and local user state.
- **`transformation_dbt/domain_data_products/.user.yml`** — Local, gitignored dbt user ID file (untracked).

### Macros

- **`transformation_dbt/domain_data_products/macros/calendar_macro.sql`** — Builds the calendar dimension through a DuckDB/BigQuery-compatible date spine, including week/month/quarter/year keys and prior-period comparisons.
- **`transformation_dbt/domain_data_products/macros/cents_to_dollars.sql`** — Adapter-dispatched conversion of integer cents to dollars, with implementations for DuckDB's default, BigQuery, Spark, Postgres, and Fabric.
- **`transformation_dbt/domain_data_products/macros/generate_schema_name.sql`** — Uses the custom schema name directly when provided, otherwise the target's default schema.
- **`transformation_dbt/domain_data_products/macros/materialization_raw_duckdb.sql`** — Custom `raw_sql` materialization for DuckDB/MotherDuck that executes the model SQL and returns its relation.
- **`transformation_dbt/domain_data_products/macros/materialization_raw_bq.sql.sql`** — BigQuery implementation of the same `raw_sql` materialization.

### XKCD models

- **`transformation_dbt/domain_data_products/models/comics/staging/_sources.yml`** — Declares the `xkcd_duckdb` source and `raw_comics_v2` table loaded by Dagster.
- **`transformation_dbt/domain_data_products/models/comics/staging/stg_comics.sql`** — Staging view that deduplicates the raw comic table by comic number.
- **`transformation_dbt/domain_data_products/models/comics/intermediate/int_comics.sql`** — Adds validated publication date, text/URL aliases, null indicators, word/character counts, and the `_key_comics` key.
- **`transformation_dbt/domain_data_products/models/comics/marts/comics.sql`** — Incremental `comics` mart keyed by `_key_comics`, with `_key_calendar` for the date dimension.
- **`transformation_dbt/domain_data_products/models/comics/marts/_comics.yml`** — Documents the comics mart and tests key uniqueness/non-null plus the calendar relationship.
- **`transformation_dbt/domain_data_products/models/comics/marts/calendar.sql`** — Table model that calls `calendar_macro` for 2006-01-01 through the current date.
- **`transformation_dbt/domain_data_products/models/comics/marts/_calendar.yml`** — Documents the calendar dimension and tests its date key.

### Jaffle Shop staging models

- **`transformation_dbt/domain_data_products/models/jaffle_shop/staging/_sources.yml`** — Declares the `ecom` source and the six seeded raw tables used by the staging models.
- **`transformation_dbt/domain_data_products/models/jaffle_shop/staging/stg_customers.sql`** — Renames raw customer columns to `customer_id` and `customer_name`.
- **`transformation_dbt/domain_data_products/models/jaffle_shop/staging/stg_customers.yml`** — Documents and tests the customer staging model.
- **`transformation_dbt/domain_data_products/models/jaffle_shop/staging/stg_locations.sql`** — Renames stores to locations and casts the opening timestamp to a date.
- **`transformation_dbt/domain_data_products/models/jaffle_shop/staging/stg_locations.yml`** — Documents and tests the location staging model.
- **`transformation_dbt/domain_data_products/models/jaffle_shop/staging/stg_order_items.sql`** — Maps raw item rows to order/item/product identifiers.
- **`transformation_dbt/domain_data_products/models/jaffle_shop/staging/stg_order_items.yml`** — Documents and tests the order-item staging model.
- **`transformation_dbt/domain_data_products/models/jaffle_shop/staging/stg_orders.sql`** — Renames order columns, converts cent amounts to dollars, and casts order dates.
- **`transformation_dbt/domain_data_products/models/jaffle_shop/staging/stg_orders.yml`** — Documents and tests the order staging model.
- **`transformation_dbt/domain_data_products/models/jaffle_shop/staging/stg_products.sql`** — Renames product fields, converts price to dollars, and derives food/drink flags.
- **`transformation_dbt/domain_data_products/models/jaffle_shop/staging/stg_products.yml`** — Documents and tests the product staging model.
- **`transformation_dbt/domain_data_products/models/jaffle_shop/staging/stg_supplies.sql`** — Creates a supply surrogate key and converts supply cost to dollars.
- **`transformation_dbt/domain_data_products/models/jaffle_shop/staging/stg_supplies.yml`** — Documents and tests the supply staging model.

### Jaffle Shop marts and seeds

- **`transformation_dbt/domain_data_products/models/jaffle_shop/marts/cafe_customers.sql`** — Builds the customer mart with lifetime order counts, repeat-buyer flag, first/last order dates, and lifetime value.
- **`transformation_dbt/domain_data_products/models/jaffle_shop/marts/cafe_customers.yml`** — Documents and tests the customer mart.
- **`transformation_dbt/domain_data_products/models/jaffle_shop/marts/cafe_locations.sql`** — Publishes the location/store dimension as a table.
- **`transformation_dbt/domain_data_products/models/jaffle_shop/marts/cafe_order_items.sql`** — Joins order items to orders, products, and supplies to calculate item revenue and cost.
- **`transformation_dbt/domain_data_products/models/jaffle_shop/marts/cafe_order_items.yml`** — Documents and tests the order-item mart.
- **`transformation_dbt/domain_data_products/models/jaffle_shop/marts/cafe_orders.sql`** — Builds the order mart with item counts, subtotal, tax, total, supply cost, and customer attributes.
- **`transformation_dbt/domain_data_products/models/jaffle_shop/marts/cafe_orders.yml`** — Documents and tests the order mart.
- **`transformation_dbt/domain_data_products/models/jaffle_shop/marts/cafe_products.sql`** — Publishes the product dimension as a table.
- **`transformation_dbt/domain_data_products/models/jaffle_shop/marts/cafe_supplies.sql`** — Publishes the supply dimension as a table.
- **`transformation_dbt/domain_data_products/seeds/raw_customers.csv`** — Jaffle Shop customer seed, loaded as `raw.raw_customers`.
- **`transformation_dbt/domain_data_products/seeds/raw_orders.csv`** — Jaffle Shop order seed, loaded as `raw.raw_orders`.
- **`transformation_dbt/domain_data_products/seeds/raw_items.csv`** — Jaffle Shop order-item seed, loaded as `raw.raw_items`.
- **`transformation_dbt/domain_data_products/seeds/raw_stores.csv`** — Jaffle Shop store/location seed, loaded as `raw.raw_stores`.
- **`transformation_dbt/domain_data_products/seeds/raw_products.csv`** — Jaffle Shop product seed, loaded as `raw.raw_products`.
- **`transformation_dbt/domain_data_products/seeds/raw_supplies.csv`** — Jaffle Shop supply seed, loaded as `raw.raw_supplies`; materializing it triggers the Jaffle transformation sensor.

## Semantic layer (`semantic_layer/`)

- **`semantic_layer/workspace/comics/`** — Credible/Publisher package for the XKCD domain: `publisher.json`, raw views, refinements, and `comics_explore`.
- **`semantic_layer/workspace/jaffle_shop/`** — Credible/Publisher package for the Jaffle Shop domain: `publisher.json`, raw views, refinements, and `cafe_explore`.
- **`semantic_layer/publisher.config.json`** — Local Publisher configuration; not uploaded to Credible or copied into the deployed image.
- **`semantic_layer/README.md`** — Package layout, connection setup, publishing rules, and the `explores` deprecation note.
- **`.github/workflows/deploy.yaml`** — On a push to `semantic_layer/workspace/**`, bumps changed package versions, publishes them to Credible, and commits the version bump with `[skip ci]`.
- **`.github/workflows/publish-packages.yml`** — Reusable Credible publish job invoked by `deploy.yaml`.
- **`.github/workflows/bump-package-versions.yml`** — Reusable version-bump job that detects changed packages and commits the new `publisher.json` versions.
- **`.github/workflows/deploy-publisher.yml`** — After a successful publish, rebuilds the Publisher image from `analytics-malloy-publisher-rag`, deploys it to Cloud Run, routes 100% of traffic to the new revision, and runs the smoke test.
- **`scripts/bump_versions.py`, `scripts/detect_changed_packages.py`, `scripts/cred_publish.sh`** — Helper scripts used by the publish workflows.

## Local documentation (not versioned)

`DOCUMENTATION/` is gitignored and kept only in the local checkout. None of these files are in GitHub or the deployed image.

- **`DOCUMENTATION/1_Research/1_Cloud Storage Selection.md`** — Research and decision record for the cloud storage choice.
- **`DOCUMENTATION/2_Plan_and_Implementation/0_PREPARATION.md`** — Preparation notes, prerequisites, and environment setup.
- **`DOCUMENTATION/2_Plan_and_Implementation/1_PROJECT.md`** — Project definition, domains, questions, and scope.
- **`DOCUMENTATION/2_Plan_and_Implementation/2_PROJECT_1_PLAN.md`** — End-to-end build and operations plan, including the monthly scale-to-zero implementation, file inventory, economics, and live deployment evidence.
- **`DOCUMENTATION/2_Plan_and_Implementation/3_PROJECT_1_Docker.md`** — Container and Cloud Run implementation notes, revision details, and deployment checks.
- **`DOCUMENTATION/2_Plan_and_Implementation/4_PROJECT_1_Schedule.md`** — Authoritative design for scheduling, Litestream, the wake endpoint, dbt docs delivery, and alerting.

## Generated and local-only files

These paths are intentionally excluded from version control or the image. They are rebuildable artifacts or local configuration, not hand-written system components.

- **`.env`** — The single local environment file (copy of `.env.example`): credentials and overrides; never commit or include in the image.
- **`transformation_dbt/domain_data_products/target/`** — dbt docs, catalog, manifest, and run results; regenerated by `dbt docs generate`/`dbt build`.
- **`transformation_dbt/domain_data_products/dbt_packages/`** — Installed dbt packages; recreated by `dbt deps`.
- **`transformation_dbt/domain_data_products/logs/`** — dbt run logs.
- **`transformation_dbt/domain_data_products/package-lock.concurrent-update-lock`** — Temporary package-lock coordination file.
- **`.venv/`, `**/__pycache__/`, `.pytest_cache/`** — Local Python environment and caches.
- **`.vscode/settings.json`** — Local VS Code workspace settings.
- **`.local_defs_state/`, `.tmp_dagster_home_*`, `$DAGSTER_HOME`** — Local/generated Dagster state and temporary homes.

