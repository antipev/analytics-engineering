# Malloy Semantic Layer: Credible, Publisher, and Cloud Run

**Date:** 2026-10-20  
**Status:** Research complete; no implementation performed  
**Scope:** Determine how to host one shared semantic layer for the `comics` and `jaffle_shop` domains across:

- `analytics-engineering` (canonical analytics repo)
- `analytics-malloy-credible` (Credible workspace)
- `analytics-malloy-publisher-rag` (self-hosted Malloy Publisher on Cloud Run)

The research question was whether cross-repository symlinks or separate folders are the right mechanism, how Credible and Publisher resolve those files, and whether a second Cloud Run service with a different URL is feasible.

---

## 1. Executive summary

| Question | Finding |
|---|---|
| Can the semantic layer live in one repo and be symlinked into the Credible repo? | **No, not across repositories.** Git stores the symlink target path, not the target contents. Credible reads the Credible repository server-side; a relative link to `analytics-engineering` will be dangling. |
| Does Credible consume a symlink from GitHub or from the laptop? | For **git-backed** environments and **CI/CD**, Credible consumes files from **GitHub**, not the laptop. A local `cred publish` reads the laptop and uploads a snapshot, but it does not create a live link, and direct publishing is refused for packages already published through git-backed modeling. |
| Can the Publisher repo symlink the same folder? | **No for Docker and Cloud Run.** The Docker build context and deployed image contain only the Publisher repo. A symlink to a sibling repo is outside the build context and will be missing or dangling. It can work only for a local Publisher process running on the same filesystem. |
| Can the semantic layer be a separate folder and be deployed to Cloud Run with a different URL? | **Yes.** Deploy a second Cloud Run service. Each service has its own image, revision, and `*.run.app` URL. Path-based routing under one domain requires an external load balancer or gateway. |
| Recommended approach | Keep `analytics-engineering` as the source of truth. Put the packages under `semantic_layer/packages/` and publish them to Credible through CI/CD. Add a second Cloud Run Publisher service only if self-hosted Publisher/MCP is actually required. Do not use cross-repo symlinks. |

---

## 2. Repositories reviewed

### 2.1 `analytics-engineering`

Observed:

- Git remote: `https://github.com/antipev/analytics-engineering.git`
- Existing Cloud Run service: `analytics-dagster`
- Region: `northamerica-northeast1`
- Existing service URL pattern: `https://analytics-dagster-bolcwt6srq-nn.a.run.app`
- `cloudbuild.yaml` builds one image from the repository root and injects `MOTHERDUCK_TOKEN` as a BuildKit secret.
- `scripts/deploy_dagster.sh` deploys the Dagster service.
- dbt models already exist for the two domains:
  - `transformation_dbt/domain_data_products/models/comics/marts/`
  - `transformation_dbt/domain_data_products/models/jaffle_shop/marts/`
- dbt target database: `data_warehouse_demo`
- Target schema: `marts`
- There is currently no `semantic_layer/` directory.
- `DOCUMENTATION/` is listed in `.gitignore`, so files created there are local-only unless force-added.

### 2.2 `analytics-malloy-credible`

Observed:

- The directory has **no `.git` directory**; it is a local Credible workspace, not a Git checkout.
- A root `publisher.json` exists, so the workspace root behaves as **one package** named `Unified_Star_Schema_Model`.
- `A_Semantic_Layer/` and `B_Published_Semantic_Layer/` are subfolders of that one package, not two independent packages.
- `B_Published_Semantic_Layer/EXPLORE/ecommerce_explore.malloy` imports:
  - `../../A_Semantic_Layer/3_models/bridge_model.malloy_hidden`
- `A_Semantic_Layer/0_data/config.malloy_hidden` currently uses a `bq_demo` connection.
- `malloy-config.json` contains a JWT access token. It is a secret and must not be committed.
- `A_Semantic_Layer/0_data/` and `malloy-config.json` are hidden through `.malloyignore`.
- There are no symlinks in this workspace.
- Credible skills are installed under `.agents/skills/`, including `credible-publish`.

Implication: adding a symlink in this local folder would not be a Git change at all, because this folder is not the repository Credible publishes from. The actual Credible repository configuration is managed server-side by the Credible environment.

### 2.3 `analytics-malloy-publisher-rag`

Observed:

- Git repository: `antipev/analytics-malloy-publisher-rag`
- Custom unified service:
  - Node `@malloy-publisher/server` running on internal ports 4000 and 5050
  - Python FastAPI/MCP/RAG gateway on the public Cloud Run port
- `Dockerfile` copies:
  - `malloy-config.json`
  - `workspace/`
  - `context/`
- `workspace/publisher.config.json` registers one package: `thelook_ecommerce`.
- The repo contains 30 tracked symlinks under `.agents/skills/`, for example:
  - `.agents/skills/malloy -> ../../.claude/skills/malloy`
- Those symlinks work because their targets are **inside the same repository**.

This is useful evidence: internal symlinks can work. External symlinks are the problem.

## 3. How Git symlinks actually behave

A Git symlink is not a copy. It is an entry with mode `120000` whose blob content is the target path. For example:

```bash
git ls-files -s | awk '$1=="120000"'
# 120000 ... .agents/skills/malloy
```

On checkout, Git creates a symlink and interprets the target relative to the symlink's location.

Example local layout:

```text
/home/maxantipev/
├── analytics-engineering/
│   └── semantic_layer/
└── analytics-malloy-credible/
    └── semantic_layer -> ../../analytics-engineering/semantic_layer
```

This works on the laptop because both directories exist as siblings.

In a Credible checkout, the layout is more like:

```text
/workspace/credible-repo/
└── semantic_layer -> ../../analytics-engineering/semantic_layer
```

`../../analytics-engineering/semantic_layer` resolves to `/analytics-engineering/semantic_layer`, which does not exist. The symlink is dangling.

The same applies to Docker:

- The Docker build context is the directory passed to `docker build`.
- `COPY` and `ADD` can access only files inside that context.
- A symlink pointing outside the context cannot be followed.
- `gcloud builds submit` uploads the selected source directory, not the whole filesystem.

### 3.1 Symlink compatibility matrix

| Symlink target | Local laptop | GitHub clone / Credible | Docker / Cloud Run |
|---|---|---|---|
| Sibling repository outside the repo | Works | **Broken** | **Broken** |
| Absolute path such as `/home/maxantipev/...` | Works | **Broken** | **Broken** |
| Target inside the same repository | Works | Usually works on Linux | Works if target is copied into the image |
| Git submodule | Works after initialization | Only if Credible initializes submodules; not documented | Only if the build explicitly initializes submodules |
| Real copied files | Works | Works | Works |

### 3.2 Verdict

Symlinks are acceptable for developer convenience inside a single repository. They are not a cross-repository packaging or deployment mechanism.

## 4. How Credible consumes files

Credible supports two relevant Git workflows, and they behave differently.

### 4.1 Git-backed modeling

Credible's GitHub App is installed on **one repository per environment**. Credible commits a draft branch, opens a pull request, and merging the pull request publishes the package.

Documented constraints:

- **One repository per environment.**
- **Each package is a top-level directory** in that repository.
- **Text files only.**
- A package containing a binary file, or a file larger than about 1 MB, is refused up front.
- Once a package has published from a merged proposal, direct uploads and `cred publish` to that package are refused.
- The source of truth is the GitHub repository, not a laptop.
- Credible's GitHub App needs:
  - Contents read/write
  - Pull requests read/write
  - Checks write
  - Metadata read

A symlink is not a regular text file, and its target is outside the repository. Even if Credible preserves the symlink during checkout, the target will not exist. It may also be skipped or rejected by the text-file rule. Cross-repo symlinks are therefore not usable for git-backed Credible packages.

### 4.2 CI/CD publishing

This is the "repository you own" path:

- A GitHub Actions workflow checks out the repository.
- It bumps each changed package's `publisher.json` version.
- It runs `cred publish` with a Credible API token.
- Credible receives the package contents from the GitHub Actions runner.
- A compile error fails the publish.

The Credible CI/CD template expects a layout like:

```text
your-repo/
├── .github/workflows/
├── packages/
│   ├── package-one/
│   │   ├── publisher.json
│   │   └── *.malloy
│   └── package-two/
│       ├── publisher.json
│       └── *.malloy
└── scripts/
```

The CLI can publish from any directory containing a `publisher.json`; the `packages/` layout is a template convention, not an absolute CLI requirement.

This is the recommended path if `analytics-engineering` must remain the source of truth. It requires no symlink and does not give Credible access to the laptop.

### 4.3 MotherDuck in Credible

Credible supports MotherDuck directly. The connection is managed in Credible:

- Connection names cannot contain spaces or hyphens; use underscores, for example `motherduck` or `md_warehouse`.
- Credentials stay in Credible.
- Every package in the environment can use the connection.
- The connection can be scoped and indexed for AI-assisted modeling.

This is a better fit than embedding Parquet files, especially because git-backed Credible packages are text-only and reject large binaries.

### 4.4 Two valid designs for `comics` and `jaffle_shop`

#### Option A: One Credible environment, two packages (recommended)

```text
analytics-engineering/
└── semantic_layer/
    └── packages/
        ├── comics/
        │   ├── publisher.json
        │   ├── index.malloy
        │   ├── comics.malloy
        │   └── calendar.malloy
        └── jaffle_shop/
            ├── publisher.json
            ├── index.malloy
            ├── customers.malloy
            ├── orders.malloy
            ├── order_items.malloy
            ├── products.malloy
            ├── locations.malloy
            └── supplies.malloy
```

Publish both packages into one Credible environment. This gives:

- One MotherDuck connection.
- Two independently versioned packages.
- Two package pages or discovery surfaces.
- Shared governance and access control.
- No duplication of connection configuration.

If Credible's CI/CD template is followed literally, rename `semantic_layer/packages/` to `packages/` at the repository root. If `semantic_layer/packages/` is kept, the workflow must `cd` into each package before `cred publish`. The CLI supports that, but it is not the template's default layout.

#### Option B: Git-backed modeling

If Credible's in-app agent must edit models and open pull requests:

- `analytics-engineering` must be the environment's **one** repository.
- Packages must be at the repository root:
  - `comics/`
  - `jaffle_shop/`
- They cannot stay under `semantic_layer/` if Credible only treats top-level directories as packages.
- The packages must be text-only.
- Merging Credible's pull request publishes.

This is more intrusive because the analytics repository also contains Dagster, dbt, documentation, and other code. A dedicated semantic-layer repository is a better fit if git-backed modeling is chosen.

#### Option C: Separate Credible repository with a real sync job

If a separate Credible repository is required, do not symlink. Use a GitHub Actions job that:

1. Checks out `analytics-engineering`.
2. Checks out the Credible repository with a token.
3. Copies package directories with `rsync`.
4. Commits and pushes a branch or pull request to the Credible repository.

Credible then sees real files, not links. The cost is duplication and a sync pipeline.

## 5. How Publisher consumes files

### 5.1 Package loading

Publisher discovers packages from `publisher.config.json`:

```json
{
  "environments": [
    {
      "name": "analytics",
      "packages": [
        { "name": "comics", "location": "./packages/comics" },
        { "name": "jaffle_shop", "location": "./packages/jaffle_shop" }
      ]
    }
  ]
}
```

A package `location` can be:

- A relative path
- An absolute path
- A `~/` path
- A `https://github.com/...`, `gs://`, or `s3://` URL

For Docker and Cloud Run, the important rule is: **the files must be inside the build context or downloadable at runtime**.

Publisher normally copies each configured package into `publisher_data/<env>/<pkg>/`. With `--watch-env`, it mounts local packages as symlinks instead. That is a local development feature, not a production packaging strategy.

### 5.2 Why a cross-repo symlink fails in Cloud Run

Example:

```text
analytics-malloy-publisher-rag/
└── workspace/
    └── semantic_layer -> ../../analytics-engineering/semantic_layer
```

Behavior:

- Locally, a Publisher process may work because the target exists on the same filesystem.
- In Docker, the build context is `analytics-malloy-publisher-rag/`; the target is outside it.
- `COPY workspace/ ./workspace/` does not bring in the sibling repository.
- In Cloud Run, only the image contents exist, so the symlink is dangling.
- In a fresh Git clone, the symlink is dangling unless the clone is placed next to `analytics-engineering` in exactly the same relative layout.

The symlink is therefore local-only and cannot be the deployment mechanism.

### 5.3 Options that work for Publisher

| Option | How it works | Trade-off |
|---|---|---|
| Copy packages into the Publisher repository before build | CI `rsync` or a build step creates `workspace/comics` and `workspace/jaffle_shop` | Duplication, but simple and reliable |
| Move Publisher into a monorepo with the semantic layer | One repository contains app and packages | Larger refactor, but one source of truth |
| Use the official Publisher image with packages baked into a small image | `FROM ms2data/malloy-publisher`, then `COPY` config and packages | Least custom code; MCP port still needs handling |
| Publisher `location` as a GitHub URL | Publisher downloads the package at runtime | Requires a public or otherwise accessible repository; network and cold-start dependency; not ideal for private packages |
| Local `--watch-env` symlink | Works on the laptop only | Not deployable |

If the existing `analytics-malloy-publisher-rag` service is kept, the cleanest approach is a CI copy step:

```bash
rsync -a --delete \
  ../analytics-engineering/semantic_layer/packages/ \
  workspace/
```

Then the existing `COPY workspace/ ./workspace/` includes real files. The copied directory can be gitignored if duplicate files should not live in Git.

### 5.4 Publisher MotherDuck configuration

Publisher supports a native `motherduck` connection type. The expected shape is:

```json
{
  "environments": [
    {
      "name": "analytics",
      "connections": [
        {
          "name": "motherduck",
          "type": "motherduck",
          "motherduckConnection": {
            "accessToken": "${MOTHERDUCK_TOKEN}",
            "database": "data_warehouse_demo"
          }
        }
      ],
      "packages": [
        { "name": "comics", "location": "./packages/comics" },
        { "name": "jaffle_shop", "location": "./packages/jaffle_shop" }
      ]
    }
  ]
}
```

Publisher resolves `${MOTHERDUCK_TOKEN}` when the configuration is loaded. In Cloud Run, inject it from Secret Manager:

```bash
--set-secrets=MOTHERDUCK_TOKEN=motherduck-token:latest
```

Malloy models would reference the MotherDuck tables:

```malloy
source: comics is motherduck.table('marts.comics') extend {
  primary_key: _key_comics
  measure: comic_count is count()
  measure: avg_transcript_words is avg(transcript_word_count)
}
```

```malloy
source: cafe_orders is motherduck.table('marts.cafe_orders') extend {
  primary_key: order_id
  measure: total_revenue is order_total.sum()
  measure: order_count is count()
}
```

With `database: data_warehouse_demo` and `attach_mode=single`, `marts.comics` is the expected two-part path. Verify the first query against the live database before publishing.

### 5.5 Publisher security warning

Publisher has **no built-in authentication**. Its documentation warns that:

- It exposes resolved connection configuration, including credentials, through its API.
- Anyone who can reach the port can run SQL through configured connections.
- A public Cloud Run deployment with a MotherDuck token is therefore dangerous.

Do not deploy Publisher with `--allow-unauthenticated` unless authentication is placed in front of it (IAP, an identity-aware proxy, or a gateway). Credible handles authentication and keeps database credentials server-side, which is a major argument for using Credible as the primary publication layer.

## 6. Cloud Run: one service or two?

### 6.1 Two services give two links

Cloud Run's unit is a **service**: one container image, one ingress port, one URL.

Existing service:

```text
analytics-dagster
https://analytics-dagster-bolcwt6srq-nn.a.run.app
```

Additional service:

```text
analytics-malloy-publisher
https://analytics-malloy-publisher-<hash>-nn.a.run.app
```

They can share:

- GCP project `my-1-st-project-training`
- Region `northamerica-northeast1`
- Artifact Registry or GCR
- Secret Manager secret `motherduck-token`
- Cloud Build triggers

They remain independent:

- Separate revisions
- Separate scaling
- Separate IAM
- Separate URLs
- Separate logs and metrics

Example deploy:

```bash
gcloud run deploy analytics-malloy-publisher \
  --project="$PROJECT_ID" \
  --region="northamerica-northeast1" \
  --image="gcr.io/$PROJECT_ID/analytics-malloy-publisher:$TAG" \
  --platform=managed \
  --port=4000 \
  --min-instances=0 \
  --max-instances=3 \
  --memory=2Gi \
  --cpu=1 \
  --cpu-boost \
  --set-secrets="MOTHERDUCK_TOKEN=motherduck-token:latest" \
  --no-allow-unauthenticated
```

Read the actual URL:

```bash
gcloud run services describe analytics-malloy-publisher \
  --region=northamerica-northeast1 \
  --format='value(status.url)'
```

### 6.2 Sidecars do not provide two public links

Cloud Run supports multiple containers in one service, but:

- Only one container is the ingress container.
- All containers share `localhost`.
- There is still only **one external URL**.

This is useful for a proxy and app pair, not for two independently addressable applications.

### 6.3 One domain with path routing

Cloud Run does not natively route `/publisher/*` to one service and `/*` to another. Use one of:

1. **External HTTPS Load Balancer**
   - One serverless NEG per Cloud Run service.
   - URL map:
     - `/publisher/*` to `analytics-malloy-publisher`
     - `/*` to `analytics-dagster`
2. **Gateway service**
   - A small nginx or Envoy Cloud Run service that proxies to the other services.
   - Adds a hop and another service to operate.

If separate hostnames are acceptable, use Cloud Run domain mappings:

- `dagster.example.com` to `analytics-dagster`
- `semantic.example.com` to `analytics-malloy-publisher`

### 6.4 Ports for Publisher

The official Publisher container uses:

- `4000` for REST and UI
- `4040` for MCP

Cloud Run routes to **one** port. Options:

- Deploy with `--port=4000` for UI and REST only.
- Add a small entrypoint or proxy that listens on `$PORT`, proxies `/mcp` to `4040`, and proxies everything else to `4000`. This is the pattern used by `analytics-malloy-publisher-rag`.
- Deploy separate UI and MCP services with different URLs, which is usually not desirable.

---

## 7. Recommended target architecture

```mermaid
flowchart TB
    GH["GitHub: antipev/analytics-engineering"]
    DBT["dbt models<br/>comics + jaffle_shop"]
    MD["MotherDuck<br/>data_warehouse_demo.marts"]
    SL["semantic_layer/<br/>packages/comics<br/>packages/jaffle_shop"]
    CRED["Credible environment<br/>MotherDuck connection"]
    PUB["Optional Cloud Run<br/>analytics-malloy-publisher"]
    DAG["Cloud Run<br/>analytics-dagster"]

    GH --> DBT
    DBT --> MD
    GH --> SL
    SL --> CRED
    SL --> PUB
    MD --> CRED
    MD --> PUB
    GH --> DAG
    DAG --> DBT
```

### 7.1 Recommended repository layout

```text
analytics-engineering/
├── ingestion/orchestration_dagster/
├── transformation_dbt/domain_data_products/
├── semantic_layer/
│   ├── README.md
│   ├── publisher.config.json
│   ├── Dockerfile.publisher
│   ├── cloudbuild.publisher.yaml
│   └── packages/
│       ├── comics/
│       │   ├── publisher.json
│       │   ├── index.malloy
│       │   ├── comics.malloy
│       │   └── calendar.malloy
│       └── jaffle_shop/
│           ├── publisher.json
│           ├── index.malloy
│           ├── customers.malloy
│           ├── orders.malloy
│           ├── order_items.malloy
│           ├── products.malloy
│           ├── locations.malloy
│           └── supplies.malloy
├── .github/workflows/publish-credible.yml   # optional
└── scripts/deploy_publisher.sh              # optional
```

`publisher.json` for each package:

```json
{
  "name": "comics",
  "version": "0.1.0",
  "description": "XKCD comics and calendar semantic model over data_warehouse_demo.marts"
}
```

```json
{
  "name": "jaffle_shop",
  "version": "0.1.0",
  "description": "Jaffle Shop cafe orders, customers, products, and locations over data_warehouse_demo.marts"
}
```

If Credible requires hyphenated names, use `jaffle-shop` as the package name while keeping the folder `jaffle_shop`.

## 8. Implementation plan (for a later Act phase)

This report does not implement the plan. The sequence below is the proposed follow-up.

### Phase 0: Finish the current migration

1. Confirm the Dagster deploy completed and the Cloud Run revision is healthy.
2. Trigger the first pipeline run so `data_warehouse_demo` recreates:
   - `ingest_xkcd`
   - `ingest_jaffle_shop`
   - `staging`
   - `marts`
3. Run dbt tests.
4. Verify the mart tables the semantic layer will read:
   - `marts.comics`
   - `marts.calendar`
   - `marts.cafe_customers`
   - `marts.cafe_orders`
   - `marts.cafe_order_items`
   - `marts.cafe_products`
   - `marts.cafe_locations`
   - `marts.cafe_supplies`

Do not publish semantic packages before `marts` exists; compilation or queries will fail.

### Phase 1: Create the semantic layer

1. Create `semantic_layer/packages/comics/` and `semantic_layer/packages/jaffle_shop/`.
2. Add `publisher.json` to each.
3. Add `index.malloy` to curate exports.
4. Add Malloy sources over `motherduck.table('marts.<table>')`.
5. Add `semantic_layer/publisher.config.json` with the `motherduck` connection.
6. Add a README covering:
   - MotherDuck dependency
   - local run instructions
   - publish instructions
   - the no-cross-repo-symlink rule

### Phase 2: Credible publication

Preferred path: CI/CD from `analytics-engineering`.

1. Create a Credible group access token or service-account JWT.
2. Add GitHub secrets and variables:
   - `CRED_JWT`
   - `CRED_ORG`
   - `CRED_ENV`
3. Add a workflow that:
   - installs `@credibledata/cred-cli`
   - authenticates with `cred set-access-token`
   - sets the environment
   - bumps each changed package's patch version
   - runs `cred publish --set-latest` in each package
4. Confirm both packages appear in Credible and compile.
5. Confirm the MotherDuck connection is used, not `bq_demo`.

Alternative: git-backed modeling, but only if packages move to top-level `comics/` and `jaffle_shop/` directories and Credible-managed pull requests in the analytics repository are acceptable.

### Phase 3: Optional self-hosted Publisher

1. Add `semantic_layer/Dockerfile.publisher`.
2. Add `semantic_layer/cloudbuild.publisher.yaml`.
3. Add `scripts/deploy_publisher.sh` modeled on `scripts/deploy_dagster.sh`.
4. Deploy a second Cloud Run service, `analytics-malloy-publisher`.
5. Inject `MOTHERDUCK_TOKEN` from Secret Manager.
6. Decide the authentication model before exposing it publicly.
7. Verify:
   - `/api/v0/status` reports `operationalState: serving`
   - `loadErrors` is empty
   - both packages are listed
   - a sample query returns rows

### Phase 4: Cleanup

1. Delete the old Malloy models from the Credible workspace when ready.
2. Update `README.md` roadmap and architecture sections.
3. Commit only source files, not `.venv`, tokens, `publisher_data/`, or generated docs.
4. Note that `DOCUMENTATION/` is gitignored; this report remains local unless force-added.

## 9. Decision matrix

| Approach | Source of truth | Duplication | Works in Credible | Works in Cloud Run | Recommendation |
|---|---|---|---|---|---|
| Cross-repo symlink | N/A | None | **No** | **No** | Do not use |
| CI copy into Credible repository | `analytics-engineering` | Yes, in Credible repo | Yes | N/A | Acceptable fallback |
| Credible CI/CD from `analytics-engineering` | `analytics-engineering` | None | Yes | N/A | **Recommended** |
| Credible git-backed on `analytics-engineering` | GitHub | None | Yes, with layout constraints | N/A | Use only with top-level packages |
| Copy into Publisher repository before build | `analytics-engineering` | Yes, in build | N/A | Yes | Good if keeping Publisher |
| Monorepo for Publisher and semantic layer | One repository | None | N/A | Yes | Best long-term if self-hosting |
| Credible only, no Publisher | Credible | None | Yes | N/A | Simplest overall |

---

## 10. Key risks and caveats

1. **Credible git-backed is one repository per environment.** Comics and `jaffle_shop` cannot live in separate repositories and still appear in the same git-backed environment.
2. **Credible git-backed packages are text-only.** Do not plan to commit Parquet seeds for those packages. Use the MotherDuck connection.
3. **Credible direct upload is refused after a git-backed package has published.** Pick one ownership model per package.
4. **Publisher has no authentication.** Do not expose it publicly with a MotherDuck token unless IAP or a gateway is added.
5. **Publisher exposes connection credentials through its API.** Treat the service as internal.
6. **Cloud Run has one ingress port per service.** Official Publisher's UI/REST and MCP ports need a proxy if both are required on one URL.
7. **Cloud Run does not do path-based routing between services.** Use an external HTTPS load balancer or a gateway.
8. **A symlink is not a copy.** If files must exist in another repository or image, copy or generate them in CI.
9. **`analytics-malloy-credible` is not a Git repository.** Changes there are not automatically part of a GitHub push; the actual Credible repository configuration is server-side.
10. **`DOCUMENTATION/` is gitignored.** This report will not be committed by default.

---

## 11. Recommended decision

For the stated goal of keeping the semantic layer in `analytics-engineering` and publishing a demo:

1. **Do not use symlinks.**
2. Create `semantic_layer/packages/comics` and `semantic_layer/packages/jaffle_shop` in `analytics-engineering`.
3. Connect **MotherDuck** in Credible and publish both packages through **Credible CI/CD** from GitHub.
4. Treat Credible as the primary website and semantic-layer surface.
5. Add a second Cloud Run Publisher service only if the self-hosted Publisher UI, MCP, or RAG is specifically required. In that case, bake copied packages into the image and secure the service.

This provides one source of truth, no dangling symlinks, no duplicated models in normal operation, and a clear path to a separate Cloud Run URL if needed.

---

## 12. References

- Credible: Git-backed modeling: https://www.credibledata.com/docs/how-to/modeling/git-backed-modeling
- Credible: Publishing: https://www.credibledata.com/docs/how-to/modeling/publishing
- Credible: CI/CD setup: https://www.credibledata.com/docs/platform-admin/cicd
- Credible: CLI: https://www.credibledata.com/docs/platform-admin/cli
- Credible: Connect a database (MotherDuck supported): https://www.credibledata.com/docs/how-to/modeling/connect-data
- Malloy Publisher: Package format: https://raw.githubusercontent.com/malloydata/publisher/main/docs/packages.md
- Malloy Publisher: Configuration: https://raw.githubusercontent.com/malloydata/publisher/main/docs/configuration.md
- Malloy Publisher: Deployment: https://raw.githubusercontent.com/malloydata/publisher/main/docs/deployment.md
- Malloy Publisher: Connections: https://raw.githubusercontent.com/malloydata/publisher/main/docs/connections.md
- Docker: Build context: https://docs.docker.com/build/building/context/
- Cloud Run: Deploying container images: https://cloud.google.com/run/docs/deploying

---

## 13. Connecting a GitHub repository and synchronising `semantic_layer`

> **Recorded:** 2026-10-20. This section preserves the full analysis delivered before implementation. The actionable, step-by-step runbook is in [`7_PROJECT_1_Credible_GitHub_Implementation.md`](./7_PROJECT_1_Credible_GitHub_Implementation.md).
>
> Heading levels were demoted by one so the recorded response nests under this section; the wording is otherwise unchanged. At the time of this record, `semantic_layer/` did not yet exist in the repository; the runbook's Phase 1 creates it.

### Short answer

**Right now there is no GitHub repository for your Credible environment to find.** I checked it directly:

```bash
cred get environment demo
```

returns:

```json
{
  "name": "demo",
  "gitModelingEnabled": false,
  "gitRepositoryOwner": null,
  "gitRepositoryName": null,
  "gitBaseBranch": null,
  "gitRepositoryRegistered": false,
  "canRecordGitRepository": true,
  "gitModelingCellEnabled": true
}
```

So:

- `https://maxantipev.admin.credibledata.com/workspaces/workspace_demo` is a **Credible workspace**, not a Git-backed environment.
- The environment is `demo`.
- It has `gitModelingEnabled: false` and no registered repository.
- There is currently **nothing to find** — no Credible-side GitHub repo exists for this environment.

Creating a GitHub repository and pushing to it **does not automatically make Credible use it**. Credible only uses GitHub when one of these is true:

1. **CI/CD publishing** — your GitHub Actions workflow checks out the repo and runs `cred publish`. Credible does not “watch” the repo; the runner uploads each package.
2. **Git-backed modeling** — you enroll the environment in git-backed modeling. Only then does Credible read the repository server-side and publish on pull-request merge.

For your goal, **CI/CD is the better fit** because it works with your current `semantic_layer/packages/` layout and needs no second repository.

---

### How you would find the repository if it were connected

#### In the Credible App

Open the environment, then **Manage environment**. The Git-backed modeling section shows:

- repository owner
- repository name
- base branch

#### With the CLI

```bash
cred status
cred status --json
cred get environment demo
```

`cred get environment` returns `gitRepositoryOwner`, `gitRepositoryName`, `gitBaseBranch`, and `gitRepositoryRegistered`. Today they are all `null` / `false`.

#### From a publish error

If a package is owned by git-backed modeling, publishing fails with `GIT_BACKED_PACKAGE_REQUIRES_DRAFT`. The error details include:

```text
gitRepositoryOwner
gitRepositoryName
gitBaseBranch
```

That names the repository Credible expects.

---

### If you create a new GitHub repo, will Credible use it?

Only after enrollment. The documented sequence is:

1. The repository must have **at least one commit** on its base branch. An empty repository has no branch for drafts to fork from.
2. Install the **Credible GitHub App** on that one repository:
   - **Only select repositories**, not all repositories
   - Contents: read/write
   - Pull requests: read/write
   - Checks: write
   - Metadata: read
3. Send Credible your **owner**, **repository name**, and **base branch**. Credible registers the repository to the environment. This is support/account-team-assisted, not self-service.
4. In the Credible App: **Manage environment → enable Git-backed modeling → enter owner, repository name, base branch → save**.

After that:

- Credible creates branches and pull requests in that repo.
- Merging the pull request publishes the new package version.
- Direct `cred publish` / upload to a package already published by a merge is refused.
- The “source of truth is GitHub, not your laptop” statement becomes true **for that enrolled environment**.

Merely creating the repo and pushing changes does not enable any of this.

---

### What I plan to append after `## 12. References`

I would add **Section 13**, immediately after line 707, with this structure:

```markdown
## 13. Connecting a GitHub repository and synchronising `semantic_layer`
```

#### 13.1 Does Credible already have a repository?

Document:

- `cred get environment demo` output.
- `gitModelingEnabled: false`, repository fields `null`.
- `workspace_demo` is a workspace, not an environment or repository.
- The current environment has only the `bq_demo` connection.

#### 13.2 Creating a repository is not connecting it

Explain the four enrollment steps above, including the GitHub App permissions and the top-level-package constraint.

Also state clearly:

- **CI/CD** does not connect the repository to Credible. It publishes snapshots from the Actions runner.
- **Git-backed modeling** connects the repository server-side and publishes on merge.
- They can coexist in one environment **package by package**, but a package already published by git-backed modeling cannot later be published by CI.

#### 13.3 Recommended architecture: CI/CD directly from `analytics-engineering`

No new repository, no copying, and no symlink:

```text
analytics-engineering
└── semantic_layer/
    └── packages/
        ├── comics/
        └── jaffle_shop/
```

Workflow behavior:

```text
push to main
  └── GitHub Actions checks out the repository
      ├── installs @credibledata/cred-cli
      ├── cred set-access-token "$CRED_JWT" -o "$CRED_ORG"
      ├── cred set environment "$CRED_ENV"
      ├── bumps each changed package's publisher.json version
      └── cd semantic_layer/packages/<package>
          └── cred publish --set-latest --yes
```

This supports the nested `semantic_layer/packages/` layout. It does not require moving packages to the repository root.

Important details to document:

- Add the MotherDuck connection first. The environment currently has only `bq_demo`.
- Store `CRED_JWT` as a GitHub secret; `CRED_ORG=maxantipev` and `CRED_ENV=demo` as repository variables.
- Do not use squash merges if you adopt Credible’s CI/CD template.
- Credible does not read your laptop. A local `cred publish` uploads a laptop snapshot; the workflow uploads a GitHub snapshot.
- The website updates after the new version is indexed; this is not instantaneous.

#### 13.4 If you specifically want a separate Credible repository

Then use a **real mirror**, not a symlink:

```text
analytics-engineering/
└── semantic_layer/packages/
    ├── comics/
    └── jaffle_shop/

                    ↓ GitHub Actions: git subtree split

semantic-layer/          ← repository registered to Credible
├── comics/
└── jaffle_shop/
```

The mirror step:

```bash
git subtree split --prefix=semantic_layer/packages -b semantic-layer-sync

git push \
  https://x-access-token:${SEMANTIC_LAYER_MIRROR_TOKEN}@github.com/antipev/semantic-layer.git \
  semantic-layer-sync:main
```

`git subtree split` makes `comics/` and `jaffle_shop/` the root of the generated branch, which is what git-backed Credible expects.

But document these caveats:

- The mirror is a **second copy**.
- `SEMANTIC_LAYER_MIRROR_TOKEN` must be a fine-grained PAT or deploy key with write access to the target repository; the analytics repository’s `GITHUB_TOKEN` cannot write to another repository.
- Direct pushes may not count as “merge” for git-backed publishing. If Credible requires a merge, the workflow must open and merge a pull request instead.
- The target repository must not be edited directly, or the next mirror overwrites those changes.
- This is more fragile than CI/CD and should only be used if git-backed in-app modeling is required.

#### 13.5 Symlink verdict

A symlink such as:

```text
semantic-layer/comics -> ../../analytics-engineering/semantic_layer/packages/comics
```

works only on the laptop. Git stores the link text, not the contents. Credible reads the repository server-side, so the link is dangling there. Docker also cannot follow links outside the build context. Use a copy/mirror, or CI/CD, not a symlink.

#### 13.6 Same pattern for the Publisher workspace

For **local development**, the Publisher can read the external package paths directly, because `publisher.config.json` locations may be relative or absolute:

```json
{
  "environments": [
    {
      "name": "theLook-DEMO",
      "connections": [],
      "packages": [
        {
          "name": "thelook_ecommerce",
          "location": "./thelook_ecommerce"
        },
        {
          "name": "comics",
          "location": "../../analytics-engineering/semantic_layer/packages/comics"
        },
        {
          "name": "jaffle_shop",
          "location": "../../analytics-engineering/semantic_layer/packages/jaffle_shop"
        }
      ]
    }
  ]
}
```

Start Publisher with `--watch-env` so edits are read live:

```bash
npx @malloy-publisher/server \
  --init \
  --server_root ./workspace \
  --port 4000 \
  --watch-env theLook-DEMO
```

But this config is machine-specific and cannot be deployed: the external paths do not exist in the Docker build context or Cloud Run image.

For **deployment**, copy real files at build time:

```bash
rsync -a --delete \
  ../analytics-engineering/semantic_layer/packages/ \
  workspace/semantic/
```

Then the production `publisher.config.json` points to:

```json
{ "name": "comics", "location": "./semantic/comics" },
{ "name": "jaffle_shop", "location": "./semantic/jaffle_shop" }
```

The existing Dockerfile already does `COPY workspace/ ./workspace/`, so the copied packages are baked into the image. Keep `workspace/semantic/` out of Git but **not** out of `.dockerignore`.

To redeploy automatically, the analytics workflow can send a `repository_dispatch` event to `analytics-malloy-publisher-rag`; that workflow checks out both repositories, runs the `rsync`, and runs `gcloud builds submit` / `gcloud run deploy`. A local-only symlink should not be committed because it breaks every clone.

#### 13.7 End state

```text
analytics-engineering (GitHub, canonical)
└── semantic_layer/packages/{comics,jaffle_shop}
        │
        ├── push to main → GitHub Actions → cred publish
        │                              → Credible environment `demo`
        │                              → workspace_demo website
        │
        └── push to main → Publisher workflow
                               → rsync packages into publisher workspace
                               → build image
                               → deploy Cloud Run revision
```

---

I have **not modified the report** because this is Plan mode. Toggle to **Act mode** and I’ll append Section 13 after `## 12. References` with the exact working commands and caveats above.

> **Recording note:** the Plan-mode limitation in the sentence above was superseded when this section was appended in Act mode. The implementation runbook is [`7_PROJECT_1_Credible_GitHub_Implementation.md`](./7_PROJECT_1_Credible_GitHub_Implementation.md).
>
> The local Publisher snippet in §13.6 is illustrative and shows an empty `connections` array. The runbook's §9.1 adds the required `motherduck` connection for these packages.
>
> **Current state (2026-10-22):** `TASK-09`, `GATE-10`, and `TASK-09a` are complete. The Publisher is deployed at revision `malloy-publisher-mcp-00031-2sd` and serves `thelook_ecommerce`, `comics`, and `jaffle_shop`; both semantic packages were re-queried through the deployed MCP endpoint. Publisher rebuild/deploy is automated by the same-repository `workflow_run` in runbook §9A; it replaces the earlier `repository_dispatch` sketch in §9.6. The workflow creates `workspace/semantic_layer/` only in the CI build context; the directory is gitignored and does not appear in the Publisher GitHub tree. The deprecated `publisher.json.explores` warning is expected and documented; the `index.malloy` migration is deferred.

## Notes of Agentic Implementation for future reference

Updated `/home/maxantipev/analytics-engineering/DOCUMENTATION/2_Plan_and_Implementation/7_PROJECT_1_Credible_GitHub_Implementation.md`.

## 1. Objective added at the top

The document now opens with an **Objective and end state** section containing your diagram and an explicit definition of done.

**Yes — that is the final objective, not an either/or choice.** The target is:

- **Credible** environment `demo` serving the packages through GitHub Actions → `cred publish`.
- **Malloy Publisher** serving a synchronized copy through its build and Cloud Run deployment.

`TASK-07` completes the Credible path. `TASK-09` completes the Publisher path. The only optional part is `TASK-08`, the git-backed modeling mirror.

Two clarifications are also recorded:

- The Publisher path can be completed manually first; the `repository_dispatch` automation in §9.6 is recommended but not required for the first deployment.
- The diagram is the target end state. It is not current state; no `semantic_layer/` directory or workflow exists yet.

## 2. Task tags and execution protocol added

Added a new section, **Execution protocol and task tags**, with:

- One tag per top-level section.
- A status model:
  - `PENDING`
  - `ACTIVE`
  - `DONE`
  - `BLOCKED`
  - `SKIPPED`
  - `N/A`
- Rules requiring one task per cycle, verification before marking `DONE`, and a stop after each tag.
- Commands such as:
  - `start TASK-01`
  - `proceed` / `next`
  - `status`
  - `retry TASK-01`
  - `skip TASK-08`
  - `rollback TASK-07`

### Tag mapping

| Tag | Section |
|---|---|
| `GATE-00` | §0 — Decisions |
| `TASK-01` | §1 — Phase 0 prerequisites |
| `TASK-02` | §2 — Package creation |
| `TASK-03` | §3 — MotherDuck connection |
| `TASK-04` | §4 — CI/CD access token |
| `TASK-05` | §5 — GitHub App, secrets, protection |
| `TASK-06` | §6 — CI/CD template adaptation |
| `TASK-07` | §7 — First Credible publish |
| `TASK-08` | §8 — Optional git-backed mirror |
| `TASK-09` | §9 — Publisher synchronization and deployment |
| `GATE-10` | §10 — End-to-end acceptance |
| `REF-11`–`REF-14` | Reference and recovery sections |

Every numbered section now has a visible tag line such as:

```text
> **Tag:** `TASK-03` | **Type:** execution | **Status:** `PENDING` | **Exit gate:** §3.4 | **Next:** `TASK-04`
```

There is also a **task board** near the top showing all tags, deliverables, exit gates, and current status. The default sequence is:

```text
GATE-00 → TASK-01 → TASK-02 → TASK-03 → TASK-04 → TASK-05
        → TASK-06 → TASK-07 → TASK-09 → GATE-10
```

`TASK-08` is explicitly optional and is skipped unless you request it.

## Important nuance

Completing both tasks makes both services operational for serving the packages, but Publisher’s separate RAG/MCP context index is not automatically updated by adding packages. That remains a documented known gap in §12. Credible and Publisher UI/query serving are the primary end-state criteria.

## Validation

- Markdown renders successfully.
- Fences balanced: 192 opening/closing markers.
- All 7 JSON blocks parse.
- All 7 YAML blocks parse.
- 15 section tag lines present.
- `DOCUMENTATION/` remains gitignored, so these changes are local unless explicitly force-added.

When you are ready to begin, the first command would be `start TASK-01`.

---
