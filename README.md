# Why?


**The Economics of Data, Analytics, and Digital Transformation by Bill Schmarzo**:
"One of the most significant impediments (`obstacles or things that slow down or block progress`) to realizing the economic value of one's data that was identified in the Economic Value of Data research was "orphaned analytics."

`Orphaned analytics` are one-off analytics developed to address a specific business need but never "operationalized" or packaged for reuse across the organization.

  - "Organizations lack an overarching framework to ensure that the resulting analytics and associated organizational intellectual capital can be captured and reused across multiple use cases. Without this over-arching analytics framework, organizations end up playing a game of analytics "whack-a-mole" where the analytics team focuses their precious and valuable resources on those immediate (urgent) problems, short-changing the larger, more strategic analytic opportunities."

"**The modern organization needs an overarching analytic module framework to help organizations to capture, share, reuse, and refine the organization's analytic `Intellectual Property (IP)`. For organizations to succeed in the 21st century, they `must invest the data science and engineering time` and discipline to master the `development of composable, reusable, continuously learning analytic modules`....that `deliver pre-defined business or operational outcomes`.**"


"The ability to leverage AI to create assets that appreciate (not depreciate) in value the more that they are used is a business and economics game-changer."


![Analytic module deployment benefits](PICTURES/Analytic%20Module%20Deployment%20Benefits.png)

 - `digitalization`, which is the integration of digital technologies such as web-based apps, mobile devices, and sensors into existing operational processes

 - `Digital Transformation`, on the other hand, leverages the growing wealth of Big Data and Internet of Things (IoT) with continuously learning AI **to uncover new customer, product, service, and operational insights (propensities)** to **reinvent the organization's business models**, to derive and drive new sources of customer, product, and operational value.

![Digital Transformation](PICTURES/Digital%20Transformation.png)



# Analytics Engineering (XKCD & Jaffle Shop example)

`Analytics engineering` turns raw, messy data into clean, tested, documented datasets. Analytics engineers package this work as **reusable analytic modules** that teams can consume for business outcomes.


This repository applies that discipline to two independent domains on one shared platform:
- Dagster for orchestration,
- MotherDuck/DuckDB for storage,
- dbt for transformation, and
- Cloud Run for delivery.


Each domain owns its ingestion path, dbt models, marts, and business logic. Both pipelines and the Malloy semantic layer are implemented end to end; the AI trend-analysis agent remains a roadmap item.

[Public access](#public-access) · [Architecture](#architecture) · [Semantic layer](#semantic-layer) · [Orchestration](#orchestration-and-delivery) · [Quick start](#quick-start) · [Repository map](REPOSITORY_MAP.md)

## Public access

| Resource | URL |
| --- | --- |
| Dagster UI | https://analytics-dagster-bolcwt6srq-nn.a.run.app/runs |
| dbt docs | https://analytics-dagster-bolcwt6srq-nn.a.run.app/dbt-docs/ |
| Health check | https://analytics-dagster-bolcwt6srq-nn.a.run.app/server_info |
| Malloy semantic layer (Publisher) | https://malloy-publisher-mcp-bolcwt6srq-nn.a.run.app |
| Credible workspace (sign-in required) | https://maxantipev.admin.credibledata.com/workspaces/workspace_demo |

## At a glance

| Domain | Business question | Source | Primary outputs |
| --- | --- | --- | --- |
| **XKCD** | How have technology, science, and gaming themes changed since 2005, and where should game development invest next? | XKCD JSON API | Incremental `comics` mart and `calendar` dimension |
| **Jaffle Shop** | How is a cafe performing across sales, customers, products, stores, and supplies? | Six CSV seeds from dbt Labs | `cafe_orders`, `cafe_customers`, `cafe_order_items`, `cafe_products`, `cafe_locations`, and `cafe_supplies` marts |

- **Implemented:** both ingestion and transformation pipelines, tests, documentation, orchestration, containerized deployment, the Malloy semantic layer, and automated Credible publishing plus Publisher rebuild/deploy.
- **Roadmap:** AI trend-analysis agent for XKCD.

## Architecture

**DWH** means **data warehouse**: the central database that stores raw, staged, and analytics-ready data and executes the transformation queries. In this project the DWH is **MotherDuck**, a cloud service built on DuckDB.

**API** means **application programming interface**: a defined way for one system to call another to exchange data or trigger an action. Three APIs are central to the architecture: the **XKCD JSON API** (external data API for comic retrieval), the **wake API** (internal control API inside the Cloud Run service, called by Cloud Scheduler), and the **Dagster GraphQL API** (internal orchestration API used by the Dagster UI and the wake API to launch and monitor runs).

```mermaid
%%{init: {"flowchart": {"subGraphTitleMargin": {"top": 0, "bottom": 20}, "nodeSpacing": 20, "rankSpacing": 24}}}%%
flowchart TB
  subgraph CONSUMERS["Data consumers<br/>people and agents that use the pipeline"]
    USER_DAG["Analyst / reviewer<br/>opens the Dagster UI and dbt docs"]
    USER_SQL["Analyst / reviewer<br/>queries MotherDuck directly with SQL"]
    USER_SEM["Analyst / reviewer<br/>queries metrics and dimensions in Malloy Publisher"]
    AGENT["AI agent<br/>queries the semantic layer over MCP"]
  end

  subgraph SOURCES["Input data sources<br/>where the pipeline gets its data"]
    XKCD["XKCD JSON API<br/>external data API for comic retrieval"]
    SEEDS["Jaffle Shop seed files<br/>six CSV files committed to GitHub"]
  end

  GH["GitHub repository<br/>source control only; Dagster, dbt, Malloy, Dockerfile, scripts"]

  subgraph OPS["Scheduling, build and operations<br/>tools and Google Cloud services that build, deploy, trigger and monitor the pipeline"]
    SCHED["Cloud Scheduler<br/>calls the wake API to start the monthly run at 08:00 UTC on the 1st"]
    CHECK["Cloud Scheduler<br/>calls the wake API to check the run result at 12:00 UTC"]
    RELEASE["Developer terminal<br/>manual: runs scripts/deploy_dagster.sh from a local checkout"]
    BOOTSTRAP["Developer terminal<br/>one-time: runs scripts/bootstrap_gcp.sh from a local checkout"]
    BUILD["Cloud Build + Docker/BuildKit<br/>builds the linux/amd64 image from Dagster + dbt source"]
    REGISTRY["Container Registry (gcr.io)<br/>stores the tagged image"]
    SM["Secret Manager<br/>stores MotherDuck, R2 and wake credentials"]
    OBS["Cloud Logging + Monitoring<br/>collects logs and metrics and sends email alerts"]
  end

  subgraph COMPUTE["Runtime - Cloud Run service<br/>runs the container image and scales to zero when idle"]
    NGINX["nginx<br/>routes public traffic to the UI, docs and wake API"]
    WAKE["wake API<br/>internal control API that starts the run and reports status"]
    DAG["Dagster runtime<br/>UI + GraphQL API<br/>assets, jobs, sensors and run state"]
    DBT["dbt runtime<br/>builds and tests staging, intermediate and mart models"]
    DOC["dbt docs<br/>static files generated during image build"]
    LS["Litestream<br/>protects run state by backing up SQLite"]
  end

  subgraph STORAGE["Object storage - two logical zones in one R2 bucket<br/>Cloudflare R2, free tier up to 10 GB"]
    R2_DATA[("R2 data zone<br/>raw_comics/{num}.json")]
    R2_STATE[("R2 backup zone<br/>Dagster SQLite replicas")]
  end

  MD[("MotherDuck data warehouse (DWH)<br/>raw, staging and mart tables")]

  MOLLOY["Semantic Layer<br/>Malloy Publisher over MotherDuck mart tables<br/>reusable metrics and dimensions from version-controlled Malloy models"]

  USER_DAG -->|"opens UI / docs"| NGINX
  USER_SQL -->|"SQL queries"| MD
  USER_SEM -->|"queries mart metrics"| MOLLOY
  AGENT -->|"MCP tool calls"| MOLLOY
  SCHED -->|"POST /wake"| NGINX
  CHECK -->|"GET /wake/status"| NGINX
  NGINX -->|"wake routes"| WAKE
  NGINX -->|"Dagster UI + GraphQL API"| DAG
  NGINX -->|"dbt docs"| DOC
  WAKE -->|"launches and monitors runs via GraphQL"| DAG
  XKCD -->|"comic JSON<br/>Dagster fetches and writes"| R2_DATA
  R2_DATA -->|"raw JSON files<br/>Dagster loads"| MD
  GH -.->|"six versioned CSV seed files"| SEEDS
  SEEDS -->|"dbt seed<br/>creates raw_* tables"| MD
  DAG -->|"runs dbt seed and model assets"| DBT
  DBT <-->|"builds and tests models"| MD
  MD -->|"mart tables"| MOLLOY
  GH -.->|"Malloy models<br/>version-controlled (planned)"| MOLLOY
  DAG -->|"writes run state"| LS
  LS <-->|"replicates and restores"| R2_STATE
  GH -.->|"manual clone / pull<br/>outside CI/CD"| RELEASE
  GH -.->|"manual clone / pull<br/>outside CI/CD"| BOOTSTRAP
  BOOTSTRAP -.->|"creates wake secret<br/>grants IAM"| SM
  RELEASE -.->|"reads wake secret"| SM
  RELEASE -.->|"gcloud builds submit ."| BUILD
  BUILD -->|"pushes tagged image"| REGISTRY
  REGISTRY -.->|"Cloud Run pulls image"| COMPUTE
  RELEASE -.->|"gcloud run deploy"| COMPUTE
  RELEASE -.->|"upserts jobs"| SCHED
  RELEASE -.->|"upserts job"| CHECK
  SM -.->|"build secret"| BUILD
  SM -.->|"runtime credentials"| COMPUTE
  COMPUTE -->|"logs and metrics"| OBS
```

MotherDuck and Dagster are shared by both domains. Object storage and the data warehouse are shown separately: the **R2** box keeps files and backups, while **MotherDuck** keeps queryable tables and runs SQL. R2 is split into two logical zones within the same bucket: the `raw_comics/` prefix is XKCD's JSON landing zone, while the `dagster_home/` prefix holds Litestream replicas of Dagster's SQLite state. The solid arrows show data lineage; Dagster executes the XKCD fetch, R2 write/read, and MotherDuck load. Jaffle Shop's raw layer is loaded into MotherDuck by `dbt seed` from the six CSV files committed to GitHub.

> **Cloud Run service, not a Cloud Run Job.** The deployed compute is a request-driven Cloud Run **service** with `min-instances=0` and `max-instances=1`. Cloud Scheduler wakes it over HTTPS; it is not a batch Cloud Run Job. See [Orchestration and delivery](#orchestration-and-delivery).

> **GitHub's role: source control, not Dagster CI/CD.** GitHub stores the Dagster code, dbt project, Dockerfile, release scripts, and seed CSVs. No GitHub Actions workflow builds or deploys the Dagster service, and there is no Cloud Build GitHub trigger for it. A developer clones or pulls the repository and runs `scripts/deploy_dagster.sh` manually from a local terminal; `gcloud builds submit .` uploads that working tree to Cloud Build, and the resulting image is deployed to Cloud Run. Automating this Dagster path is a roadmap item. The separate semantic-layer publish/deploy path is automated; see [`semantic_layer/README.md`](./semantic_layer/README.md).

> **How Secret Manager is populated.** `scripts/bootstrap_gcp.sh` is a shell script run manually once from a developer terminal — not by Docker or Cloud Build. It enables Secret Manager, creates `wake-shared-secret`, and grants the runtime and build identities access. The MotherDuck and R2 secrets must already exist; create them manually with `gcloud secrets create` or the Google Cloud console. Cloud Build then consumes `motherduck-token` at build time, while `scripts/deploy_dagster.sh` reads `wake-shared-secret` and passes runtime secret references to Cloud Run.

> **Docker's role: build, not runtime.** Docker is not a separate deployed service. The `Dockerfile` defines the image, `cloudbuild.yaml` runs `docker build` with BuildKit inside Cloud Build, Cloud Build pushes the tagged image to Container Registry, and `scripts/deploy_dagster.sh` deploys that image to the Cloud Run service. Cloud Run runs the resulting container; there is no Docker daemon inside the service.

> **dbt: packaged at build time, executed at runtime.** The dbt project (models, seeds, tests, macros) is copied into the image and `dbt deps` plus `dbt docs generate` run during the image build, but no warehouse transformations or data tests run then. At runtime, Dagster launches the dbt assets, which build and test the models against MotherDuck. The diagram therefore keeps **dbt runtime** in the Cloud Run group.

### Component responsibilities

| Functional role | Technology | Responsibility |
| --- | --- | --- |
| **Input sources** | XKCD JSON API (external data API); six Jaffle Shop CSV seed files | Provide the two domains' source data. |
| **Source control** | [GitHub repository](https://github.com/antipev/analytics-engineering) | Stores Dagster code, dbt models/seeds/tests, Dockerfile, release scripts, and seed CSVs. Bootstrap and release are manual from a developer terminal; there is no GitHub Actions or Cloud Build trigger. |
| **Scheduling** | Cloud Scheduler | Starts `POST /wake` monthly at 08:00 UTC and checks `GET /wake/status` at 12:00 UTC; retries failures. |
| **Container image** | Dockerfile + Docker/BuildKit | Packages Dagster and dbt source, generated static dbt docs, Python 3.12, nginx, and Litestream into the `linux/amd64` image. |
| **Build and release** | Developer terminal + Cloud Build + Container Registry + `scripts/deploy_dagster.sh` | The release script is run manually and submits the local checkout to Cloud Build, which runs the Docker build and pushes the tagged image; the script then deploys it to Cloud Run and upserts both Scheduler jobs. |
| **Container compute** | Cloud Run service (one container, min 0 / max 1) | Runs the packaged image: nginx, wake API, Dagster runtime, dbt runtime, static dbt docs, and Litestream; scales to zero when idle. |
| **HTTP entry point** | nginx | Routes public traffic to the Dagster UI/GraphQL API, static dbt docs, and the wake endpoints. Cloud Run terminates TLS at the edge. |
| **Run control** | Starlette/uvicorn wake API (internal control API) | Authenticates Scheduler, calls Dagster's GraphQL API to launch the monthly ingestion idempotently, waits for the sensor-triggered transformation, and reports status. |
| **Orchestration** | Dagster runtime (webserver + GraphQL API) | Defines assets, jobs, the monthly schedule, and two asset sensors; serves the UI and GraphQL API; stores run and schedule state in SQLite. |
| **Transformation** | dbt runtime | Executes only when Dagster launches the dbt assets; builds staging/intermediate/mart models and runs tests against the DWH. |
| **Data warehouse (DWH)** | MotherDuck on DuckDB (free tier 10 GB for individuals) | Stores queryable raw, staging, and mart tables and executes dbt SQL. |
| **Semantic layer** | Malloy Publisher + Credible | Publishes reusable metrics and dimensions over the MotherDuck mart tables, managed from the `semantic_layer/workspace/` packages and deployed automatically after a successful Credible publish. |
| **Object storage** | Cloudflare R2 (free tier up to 10 GB) | Two logical zones in one bucket: `raw_comics/` stores raw XKCD JSON, and `dagster_home/` stores Litestream backups of Dagster's SQLite state. |
| **State protection** | Litestream + restore script | Replicates SQLite continuously and restores run history and schedule state before Dagster starts on a cold instance. |
| **Configuration** | Secret Manager + environment variables | `bootstrap_gcp.sh`, run manually, creates `wake-shared-secret` and grants IAM; MotherDuck and R2 secrets must exist beforehand. Cloud Build reads `motherduck-token` for build-time dbt docs; the deploy script reads `wake-shared-secret` and injects runtime secret references into Cloud Run. No secret is baked into the image. |
| **Observability** | Cloud Logging + Cloud Monitoring | Converts failure logs into metrics and sends email alerts. |

### Monthly request path

1. **08:00 UTC on the 1st:** Cloud Scheduler sends an authenticated `POST /wake` to the wake API. Cloud Run starts the container from zero if needed, restores Dagster state from R2, and starts nginx, Dagster, the wake API, and Litestream.
2. **Ingestion:** the wake API launches `comics_ingestion_job` idempotently. Dagster downloads only missing comics from the XKCD API into R2, then loads them into `MotherDuck.ingest_xkcd.raw_comics_v2`.
3. **Transformation:** materializing `raw_comics_v2` fires the asset sensor, which launches `comics_transformation_job`. dbt builds and tests the staging, intermediate, and mart models in MotherDuck.
4. **Confirmation:** `/wake` waits for both runs and returns success only when both succeed. At **12:00 UTC**, a second Scheduler job calls `GET /wake/status` as a dead-man's-switch; failures produce structured logs and email alerts.
5. **Idle:** the service scales back to zero. MotherDuck keeps the analytics tables; R2 keeps raw JSON and the replicated Dagster run/schedule state.

## Domain 1 — XKCD

**Business question.** How did public interest in technology, science, and gaming culture shift over two decades, and which directions are most likely to succeed in game development?

**Why it matters.** Tracking themes year by year helps identify topics with adoption potential, reducing the financial risk of new game concepts.

![xkcd.com comic #1017, "Backward in Time"](PICTURES/Comics.png)

*[xkcd.com](https://xkcd.com/) is the source for this domain; the JSON API provides each comic's title, date, and transcript.*

**Pipeline.**
- On the first day of each month at 08:00 UTC, Cloud Scheduler calls `POST /wake`. The endpoint launches `comics_ingestion_job` and waits for the sensor-triggered transformation. The in-code Dagster schedule exists but is stored as `STOPPED`; Cloud Scheduler is the single monthly trigger.
- The job reads the latest comic number from the XKCD API, compares it with the IDs already stored in R2, and downloads only the gaps. Comic #404 is skipped because the site returns its "not found" page for that ID.
- Downloads use a 20-worker thread pool and write one JSON file per comic under `raw_comics/`. A `full_refresh` option re-downloads everything.
- A second asset loads missing R2 files into MotherDuck in batches as `ingest_xkcd.raw_comics_v2`. Raw JSON remains in R2; MotherDuck holds the queryable copy.
- dbt moves the data through `stg_comics` and `int_comics` into an incremental `comics` mart keyed by comic number, plus a `calendar` dimension.

**Outputs.** A tested, documented comics mart ready for keyword and trend analysis. Sources: [xkcd.com](https://xkcd.com/) · [JSON API](https://xkcd.com/info.0.json).

## Domain 2 — Jaffle Shop

**Business question.** How is the cafe performing across sales, customers, products, stores, and supplies?

**Why it matters.** Operators need one consistent view of revenue, order composition, customer lifetime value, product and store performance, and supply costs instead of manual spreadsheet reporting.

![The Jaffle Shop project on GitHub](PICTURES/JaffleShop.png)

*The [dbt Labs Jaffle Shop](https://github.com/dbt-labs/jaffle-shop) sample project is the source for the cafe domain: its six CSV seeds load into `ingest_jaffle_shop`.*

**Pipeline.**
- Six CSV seeds from the [dbt Jaffle Shop project](https://github.com/dbt-labs/jaffle-shop) load into MotherDuck's `ingest_jaffle_shop` schema: `raw_customers`, `raw_orders`, `raw_items`, `raw_stores`, `raw_products`, and `raw_supplies`.
- The seed assets are chained in that order to avoid concurrent schema creation and write conflicts.
- Materializing the final seed, `raw_supplies`, triggers `jaffle_shop_transformation_job`.
- dbt builds staging models and six `cafe_` marts: `cafe_customers`, `cafe_orders`, `cafe_order_items`, `cafe_products`, `cafe_locations`, and `cafe_supplies`.

**Outputs.** A tested, documented cafe analytics layer covering the full sales and operations lifecycle.

## Semantic layer

The semantic layer sits on top of the dbt marts in MotherDuck. It is version-controlled under `semantic_layer/workspace/` and published as two Malloy packages, `comics` and `jaffle_shop`. Credible builds and versions each package from `1_raw_views`, `2_refinements`, and `3_explores`; Malloy Publisher serves the compiled explores for interactive analysis and MCP access by AI agents. Pushes to `semantic_layer/workspace/**` trigger the GitHub Actions publish and Publisher rebuild/deploy path.

![MotherDuck schemas used by the semantic layer](PICTURES/Mother%20Duck.png)

*MotherDuck holds the raw and transformed tables; the semantic packages read the `marts` schema in `data_warehouse_demo`.*

![Credible comics package at version 0.1.2](PICTURES/Credible.png)

*Credible tracks the `comics` package as a versioned build with raw views, refinements, and the published explore.*

![Malloy Publisher querying comics_explore](PICTURES/Malloy%20Publisher.png)

*Malloy Publisher runs `comics_explore` against MotherDuck and returns yearly comic counts and transcript-word measures.*

## Orchestration and delivery

| Domain | Ingestion job | Transformation job | Trigger |
| --- | --- | --- | --- |
| XKCD | `comics_ingestion_job` | `comics_transformation_job` | Cloud Scheduler `POST /wake` at 08:00 UTC on the 1st; sensor on `raw_comics_v2` |
| Jaffle Shop | `jaffle_shop_ingestion_job` | `jaffle_shop_transformation_job` | Manual/local run; sensor on `raw_supplies`, the final seed |

```mermaid
sequenceDiagram
  autonumber
  participant S as Schedule / sensor
  participant D as Dagster runtime / GraphQL API
  participant X as XKCD JSON API
  participant R as R2
  participant M as MotherDuck
  participant T as dbt runtime

  S->>D: comics_ingestion_job
  D->>X: fetch latest + missing IDs
  X-->>D: JSON
  D->>R: write raw_comics/{num}.json
  D->>M: load ingest.raw_comics_v2
  D-->>S: raw_comics_v2 materialized
  S->>D: comics_transformation_job
  D->>T: transform
  T->>M: build staging/intermediate/marts
```

Jaffle Shop follows the same handoff pattern: six chained seeds replace the XKCD API/R2 step, and the final seed triggers its transformation job.

![Dagster global asset lineage for the XKCD and Jaffle Shop domains](PICTURES/Dagster%20Lineage.png)

*Dagster's global asset lineage shows both domains, from raw assets through their final marts.*

```mermaid
flowchart LR
  subgraph CR["Runtime - Cloud Run service<br/>runs the container image, scales to zero when idle"]
    N["nginx :$PORT<br/>public entry point and router"]
    N -->|/runs| D["Dagster<br/>UI, GraphQL API and orchestration"]
    N -->|/dbt-docs| DOC["dbt docs<br/>static files built into the image"]
    N -->|/wake| W["wake API<br/>internal control API for runs"]
    SUP["supervisord<br/>keeps all processes running"] -. manages .-> N
    SUP -. manages .-> D
    SUP -. manages .-> W
    SUP -. manages .-> L["Litestream<br/>backs up SQLite state"]
    DBT["dbt runtime<br/>builds and tests data"]
  end

  U["Browser / Cloud Scheduler<br/>people and automated triggers"] --> N
  W -->|"launches / polls runs (GraphQL)"| D
  D -->|"writes raw JSON"| R2_DATA[("Cloudflare R2<br/>raw JSON data zone")]
  D -->|"loads raw tables"| MD[("MotherDuck DWH<br/>queryable tables")]
  D -->|"runs dbt"| DBT
  DBT <-->|"builds and tests models"| MD
  D -->|"writes run state"| L
  L -->|"replicates state"| R2_STATE[("Cloudflare R2<br/>SQLite backup zone")]
```

- nginx exposes the public Cloud Run port and proxies `/runs`, `/dbt-docs/`, `/wake`, and `/wake/status`.
- dbt project code is copied into the image at build time; transformations and tests execute only when Dagster launches the dbt assets.
- dbt docs are generated at image-build time and served as static files, so a cold start does not need to query MotherDuck for catalog metadata.
- `/wake` is authenticated with the `X-Wake-Secret` header and can wait up to 25 minutes (1500 seconds), behind a 30-minute Scheduler and proxy deadline.
- Litestream replicates Dagster's SQLite databases to the R2 backup zone; the entrypoint restores them before Dagster starts. Raw XKCD JSON lives in the R2 data zone.
- The dbt assets and seed assets expose a runtime `full_refresh` option for selected rebuilds.

## Validation

| Check | Result |
| --- | --- |
| `dg list defs` | Resolves four domain-scoped jobs, two sensors, and one schedule |
| `dbt parse --target motherduck_dev` | Validates the dbt project |
| Local XKCD run | 3,302 comics loaded and 3,302 rows in the comics mart; counts grow with each scheduled run |
| MotherDuck raw table | `ingest_xkcd.raw_comics_v2` |
| Cloud Run | One container serves the Dagster UI and dbt docs |

![dbt docs showing the xkcd_duckdb.raw_comics_v2 source, its description, columns, and Dagster asset key](PICTURES/DBT%20Documentation.png)

*dbt docs expose source descriptions, columns, and the linked Dagster asset key.*

## Quick start

### Local

```bash
cp .env.example .env        # repository root; fill in GCP, R2, and MotherDuck values
uv venv .venv --python 3.10 # first time only; one environment for the whole repo
source .venv/bin/activate
uv sync --project ingestion/orchestration_dagster --active
cd ingestion/orchestration_dagster
dg dev
```

Open `http://localhost:3000` and run `comics_ingestion_job` or `jaffle_shop_ingestion_job`.

The repository-root `.venv` is the single environment for the whole project. It contains Dagster, dbt, and every dependency from `ingestion/orchestration_dagster/uv.lock`. Because `uv` normally creates the environment next to `pyproject.toml`, dependency updates must be synced into the active root environment with `uv sync --project ingestion/orchestration_dagster --active`. Run `dg` and `dbt` from `ingestion/orchestration_dagster` so Dagster finds its `defs` directory.

`.env` in the repository root is the single environment file. Dagster loads it through `python-dotenv` (the loader walks up from the project directory), and `scripts/bootstrap_gcp.sh` / `scripts/deploy_dagster.sh` source it automatically. For dbt CLI commands, load it into the shell first from the repository root: `set -a; source .env; set +a`.

## Repository map

The full file-by-file inventory is in [REPOSITORY_MAP.md](REPOSITORY_MAP.md). It covers the root/build/deployment files, Docker runtime, Dagster orchestration, dbt project, semantic layer, documentation, and generated/local-only paths.

## Roadmap

- **AI trend-analysis agent for XKCD** — consumes the comics mart to produce trend analyses and strategic input for game development. Not implemented yet.
- **Dagster release automation** — the Dagster image is still built and deployed manually with `scripts/deploy_dagster.sh`. Semantic-layer publish/deploy is already automated by GitHub Actions; extending that pattern to the Dagster service remains optional work.
