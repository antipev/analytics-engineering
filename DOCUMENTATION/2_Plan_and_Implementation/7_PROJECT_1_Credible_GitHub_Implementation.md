# Project 1 — Credible GitHub integration and `semantic_layer` synchronisation

> **Status:** implementation runbook. The repository inspection and Credible checks below were executed on 2026-10-20; the Phase 1 file changes, the Phase 2 MotherDuck connection, the Phase 3 CI/CD group and token, the Phase 4 GitHub App, secrets, variables, and `main` ruleset, the Phase 5 CI/CD template and path adaptations are applied, and the Phase 6 first Credible publish is complete. PR #1 merged the workflow and package metadata changes; run `39508584228` published `comics@0.1.1` and `jaffle_shop@0.1.1`.
>
> **Execution status:** `TASK-01` through `TASK-07`, `TASK-09`, and `GATE-10` are `DONE`. `TASK-05` created and installed the App `credible-analytics-eng-cicd` (App ID `5402661`, installation ID `173548695`), set all three repository secrets, and configured the active `main-protection` ruleset with the App as an always-bypass actor. The repository-admin role was added as a second always-bypass actor during `TASK-07` so the sole maintainer can push and merge their own PR with `--admin`; GitHub still forbids approving your own PR. `TASK-06` installed the CI/CD template from commit `5e6b2be` and adapted it to `semantic_layer/workspace/**` and `CRED_JWT`. `TASK-07` merged PR #1 and published both packages at `0.1.1` (`buildStatus: READY`, `indexStatus: indexed`). `TASK-09` synced the packages into the Publisher image, built image digest `sha256:8ba5a3eb...` with Cloud Build, deployed revision `malloy-publisher-mcp-00028-ric`, and verified both packages query over the deployed MCP endpoint. `GATE-10` re-verified both serving paths on 2026-10-21 through the Credible Data API and the deployed Publisher MCP. `TASK-09a` is `DONE` (2026-10-22): WIF and repository secrets were created, `.github/workflows/deploy-publisher.yml` was merged, and both the manual and automatic paths were proven. A real package commit (`f4a5b6b`) started publish run `39696122370`; the bot bump `a6e1383` then started deploy run `39696218691`, which built `sha-a6e13834b61d` and deployed revision `malloy-publisher-mcp-00029-fzp`. MCP queries, version parity, rollback to `00028-2nc`, and a failed-publish safety check were all verified. The recovery deploy exposed a stale-traffic risk in the smoke test; `fb46b1c` added an explicit routing assertion, validated by manual run `39699737003`, and the current revision is `malloy-publisher-mcp-00031-2sd` at 100%.
>
> **Related:** [`6_PROJECT_1_Malloy_Semantic_Layer.md`](./6_PROJECT_1_Malloy_Semantic_Layer.md), especially §13.
>
> **Day-to-day changes:** [`ADMIN_MERGE_QUICK_REFERENCE.md`](./ADMIN_MERGE_QUICK_REFERENCE.md) — the exact branch → PR → `gh pr merge --admin` sequence used for every change.
>
> **Goal:** make the Credible environment `demo` serve the `comics` and `jaffle_shop` Malloy packages whose source of truth is `antipev/analytics-engineering`, and make the self-hosted Malloy Publisher serve the same packages.

---

## Objective and end state

**Final objective:** keep one canonical copy of the `comics` and `jaffle_shop` Malloy packages in `antipev/analytics-engineering`, and serve that source through **both** consumption paths:

1. **Credible** — environment `demo`, visible at the `workspace_demo` website.
2. **Malloy Publisher** — the self-hosted Publisher, built from a copy of the same packages and deployed to Cloud Run.

A merge to `main` is the single change trigger. The delivery paths are independent: Credible receives uploaded package versions, while Publisher receives files in its build context. Neither path reads the other's copy.

```text
analytics-engineering (GitHub, canonical)
└── semantic_layer/workspace/{comics,jaffle_shop}
        │
        ├── push to main → GitHub Actions → cred publish
        │                              → Credible environment demo
        │                              → workspace_demo website
        │
        └── push to main → Publisher workflow
                               → rsync packages into publisher workspace
                               → build image
                               → deploy Cloud Run revision
```

The Publisher path can start manually with the `rsync` + build + deploy steps in §9. The `repository_dispatch` workflow in §9.6 was the original optional sketch; §9A replaces it with a same-repository `workflow_run` design that requires no cross-repository token. Automation is recommended, but the end state is both services serving the packages; the first successful deployment did not depend on the dispatch workflow.

**Definition of done:**

- [x] Both packages live in `semantic_layer/workspace/` and are the only source of truth.
- [x] A merge to `main` publishes new versions to Credible `demo` automatically.
- [x] Credible serves both packages from the `motherduck` connection, and queries succeed in `workspace_demo`. Both versions are `READY` and indexed.
- [x] The Publisher workspace contains a synchronized copy of both packages, and the deployed revision serves them without load errors.
- [x] No secret, token, generated package copy, or absolute laptop path is committed.

**Scope confirmation:** yes — this is the final objective, not an either/or choice. `TASK-07` completes Credible, and `TASK-09` completes Malloy Publisher. The only optional part is `TASK-08`, the git-backed modeling path.

**Scope note:** the optional git-backed modeling path in Phase 7 is **not required** for this end state. It is an alternative ownership model for teams that want to edit models in the Credible App. If enabled, it replaces CI ownership for the enrolled package; CI and git-backed publishing must not own the same package.

---

## Execution protocol and task tags

This runbook is intentionally **not** executed in one pass. Each top-level section has a task tag. Execute one tag, verify it, mark it, stop, and wait for the next command.

### Tag rules

1. Tags follow the section number. `TASK-01` is §1 (Phase 0); `TASK-09` is §9 (Phase 8).
2. Work on exactly one tag per cycle unless explicitly told to combine tags.
3. Read the whole tagged section before changing anything.
4. Run its steps and its verification checklist. Judge completion from observed output, not from intent.
5. Mark the tag `DONE` only when every checklist item passes. Otherwise mark it `BLOCKED` and stop.
6. Update the status in **both** the tag line under the section and the task board below.
7. Stop and report the tag, status, evidence, blockers, and next tag. Do not continue automatically.
8. `TASK-08` is optional and must be explicitly requested. The default path skips it.
9. `REF-*` sections are reference material and do not complete as tasks. `REF-11` must be updated before enabling `TASK-08` and again at `GATE-10`.

### Status values

| Status | Meaning |
| :--- | :--- |
| `PENDING` | Not started. |
| `PLANNED` | Design documented and awaiting approval; no implementation or cloud changes yet. |
| `ACTIVE` | Currently being executed. |
| `DONE` | All exit criteria observed; tag line and board updated. |
| `BLOCKED` | A check failed; work stopped; blocker recorded. |
| `SKIPPED` | Optional task intentionally skipped (`TASK-08` only). |
| `N/A` | Reference section; no completion state. |

### Commands

| Command | Effect |
| :--- | :--- |
| `start TASK-01` | Execute only that tag. |
| `proceed` / `next` | Start the next pending task in the default sequence. |
| `status` | Report the task board without changing anything. |
| `retry TASK-01` | Re-run verification for a blocked or failed tag. |
| `skip TASK-08` | Mark the optional task skipped; only on explicit instruction. |
| `rollback TASK-07` | Use §13 to reverse that task, then update its tag. |

### Default sequence

`GATE-00` → `TASK-01` → `TASK-02` → `TASK-03` → `TASK-04` → `TASK-05` → `TASK-06` → `TASK-07` → `TASK-09` → `GATE-10` → `TASK-09a`

`TASK-08` is optional. If requested, run it after `TASK-07` and before `GATE-10`, and update `REF-11` before enrollment.

### Task board

| Tag | Section | Type | Deliverable | Exit gate | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `GATE-00` | §0 | Decision gate | Confirm the CI/CD baseline and whether `TASK-08` is in scope | Decisions table reviewed | `PENDING` |
| `TASK-01` | §1 | Execution | Repository, marts, environment, and permission baseline | §1.5 | `DONE` |
| `TASK-02` | §2 | Execution | Both packages created, locally validated, and dry-run | §2.9 | `DONE` |
| `TASK-03` | §3 | Execution | MotherDuck connection in `demo` | §3.4 | `DONE` |
| `TASK-04` | §4 | Execution | Dedicated `credible-ci` group and token | §4.4 | `DONE` |
| `TASK-05` | §5 | Execution | GitHub App, secrets, variables, and `main` ruleset | §5.6 | `DONE` |
| `TASK-06` | §6 | Execution | Adapted CI/CD template | §6.7 | `DONE` |
| `TASK-07` | §7 | Execution | First successful Credible publish and verification | §7.9 | `DONE` |
| `TASK-08` | §8 | Optional | Git-backed mirror enrollment | §8.8 | `SKIPPED` |
| `TASK-09` | §9 | Execution | Publisher synchronization, image, and deployment | §9.9 | `DONE` |
| `TASK-09a` | §9A | Execution | Automate Publisher rebuild/deploy after a successful Credible publish | §9A.7 | `DONE` |
| `GATE-10` | §10 | Acceptance gate | End-to-end acceptance for both services | §10.1–§10.4 | `DONE` |
| `REF-11` | §11 | Decision record | Final ownership matrix | Filled before `TASK-08` and at `GATE-10` | `DONE` |
| `REF-12` | §12 | Reference | Known gaps and open items | Re-check during every task | `N/A` |
| `REF-13` | §13 | Recovery reference | Rollback and recovery | Used only on failure | `N/A` |
| `REF-14` | §14 | Reference | Command lookup | No task completion by itself | `N/A` |

---

## 0. Decisions at a glance

> **Tag:** `GATE-00` | **Type:** decision gate | **Status:** `PENDING` | **Exit gate:** this table and the chosen path are reviewed.

| Question | Decision in this runbook |
| :--- | :--- |
| Does Credible already have a GitHub repository for `demo`? | No. `gitModelingEnabled` is `false`; all repository fields are `null`; `gitRepositoryRegistered` is `false`. |
| Does creating a GitHub repository connect it to Credible? | No. CI/CD publishes from a runner; git-backed modeling requires support-assisted enrollment and a GitHub App installation. |
| Which path is recommended? | **CI/CD from `analytics-engineering`.** It preserves `semantic_layer/workspace/` and needs no second repository. |
| Does the official CI/CD template work unchanged with `semantic_layer/workspace/`? | **No.** Its detection and publish scripts assume a root `packages/` directory. Phase 5 documents the exact changes. |
| Can a symlink connect the Publisher or Credible to the packages? | **No.** Git stores link text, and Docker/Credible cannot traverse outside their checkout or build context. |
| Is git-backed modeling still possible? | Yes, but only as an optional second path, normally with a dedicated mirror repository whose package directories are at the root. |
| Should both paths be enabled for the same package? | **No.** Once a package has published through git-backed modeling, direct uploads and CI publishes to that package are refused. Choose an owner per package. |
| Where is the current source of the packages? | **Nowhere yet.** `analytics-engineering` has no `semantic_layer/` directory as of the inspection date. Phase 1 creates it. |

### 0.1 Two meanings of “sync”

```text
CI/CD sync (recommended)
  GitHub push → Actions runner → cred publish → Credible environment
  Credible never reads the repository.

Git-backed sync (optional)
  GitHub repository → Credible GitHub App → draft branch / pull request
  Merge → Credible publishes → Credible serves the merged version.
```

They are independent mechanisms. CI/CD is a deployment pipeline; git-backed modeling is an ownership and review model inside Credible.

---

## 1. Phase 0 — Prerequisites and baseline checks

> **Tag:** `TASK-01` | **Type:** execution | **Status:** `DONE` | **Exit gate:** §1.5 | **Next:** `TASK-02`

Do not start with GitHub configuration. A publish cannot succeed until the warehouse connection and mart tables exist.

### 1.1 Verify the source repository

```bash
cd /home/maxantipev/analytics-engineering

git remote -v
git branch --show-current
git status --short
git log -1 --oneline
```

Expected:

```text
origin  https://github.com/antipev/analytics-engineering.git (fetch)
origin  https://github.com/antipev/analytics-engineering.git (push)
main
```

A clean working tree is required before adding workflow files.

Confirm whether the semantic layer already exists:

```bash
test -d semantic_layer/workspace && echo "semantic_layer exists" || echo "semantic_layer missing"
find semantic_layer -maxdepth 3 -type f 2>/dev/null | sort
```

On the inspection date both commands showed **missing / no files**. Phase 1 must therefore create the directory rather than modify an existing one.

### 1.2 Verify the dbt marts in MotherDuck

The semantic packages read `data_warehouse_demo.marts`. Confirm these tables exist before publishing:

```bash
cd /home/maxantipev/analytics-engineering
set -a
source .env
set +a

python - <<'PY'
import os

import duckdb

con = duckdb.connect(
    "md:",
    config={"motherduck_token": os.environ["MOTHERDUCK_TOKEN"]},
)
rows = con.execute(
    """
    select table_schema, table_name
    from information_schema.tables
    where table_catalog = 'data_warehouse_demo'
      and table_schema = 'marts'
    order by table_name
    """
).fetchall()
for schema, table in rows:
    print(f"{schema}.{table}")
PY
```

Required tables:

```text
marts.calendar
marts.cafe_customers
marts.cafe_locations
marts.cafe_order_items
marts.cafe_orders
marts.cafe_products
marts.cafe_supplies
marts.comics
```

If any are missing, stop and finish the Dagster/dbt run first. A package that compiles against a missing table will fail to publish or fail when queried.

### 1.3 Verify the Credible environment and connections

```bash
cred --cli-version
cred status
cred get environment demo
cred ls connection
```

Verified baseline on 2026-10-20:

- CLI version: `0.0.102`.
- Environment: `demo`.
- `gitModelingEnabled: false`.
- `gitRepositoryOwner`, `gitRepositoryName`, `gitBaseBranch`: `null`.
- `gitRepositoryRegistered: false`.
- `canRecordGitRepository: true`.
- Connections: **`bq_demo` only** (`type: bigquery`).

At baseline inspection time there was no MotherDuck connection. `TASK-03` added one.

### 1.4 Permissions checklist

- [x] Organization admin or a user allowed to create connections in Credible. (`userPermission: admin` on `demo`)
- [x] Admin access to `antipev/analytics-engineering` on GitHub. (GitHub API reports `admin: true`)
- [x] Permission to create a GitHub App in the account or organization. (Confirmed by account/repo admin; App creation is exercised in `TASK-05`.)
- [x] Permission to create repository secrets and variables. (Repository admin)
- [x] Permission to edit branch protection for `main`. (Repository admin; no protection is currently configured.)
- [x] MotherDuck token available in the local `.env` (for verification only; never commit it).

### 1.5 Stop conditions

Do not continue past Phase 0 if any of these is true:

- The marts listed in §1.2 are missing.
- The Credible environment has no MotherDuck connection and you cannot create one.
- You cannot create a GitHub App with **Contents: Read and write**.
- The repository is not `antipev/analytics-engineering` or you cannot push to its `main` branch.
- You intend to use git-backed modeling and the packages will remain nested under `semantic_layer/workspace/`.

### 1.6 Execution evidence — 2026-10-20

- `origin` is `https://github.com/antipev/analytics-engineering.git`; branch is `main`; working tree is clean; HEAD is `f988a34`.
- `semantic_layer/workspace` was **missing at inspection time**. `TASK-02` created it.
- MotherDuck returned all 8 required `marts` tables: `calendar`, `comics`, and six `cafe_*` tables.
- Credible CLI is `0.0.102`; organization is `maxantipev`; environment is `demo`; `userPermission` is `admin`.
- At baseline inspection time, `demo` had only the `bq_demo` connection; no `motherduck` connection yet. `TASK-03` added it.
- `gitModelingEnabled` is `false`; all Git repository fields are `null`; `gitRepositoryRegistered` is `false`.
- GitHub reports `admin: true` for `antipev/analytics-engineering`. Branch protection for `main` is currently absent and will be configured in `TASK-05`.
- No stop condition in §1.5 is triggered for the default CI/CD path. `TASK-08` remains optional.

### 1.7 Stop gate

**Decision:** `TASK-01` is complete. Proceed only when the user explicitly starts `TASK-02`.

---

## 2. Phase 1 — Create and validate the two packages

> **Tag:** `TASK-02` | **Type:** execution | **Status:** `DONE` | **Exit gate:** §2.9 | **Next:** `TASK-03`

### 2.1 Create the layout

From `/home/maxantipev/analytics-engineering`:

```bash
mkdir -p semantic_layer/workspace/comics/1_raw_views
mkdir -p semantic_layer/workspace/comics/2_refinements
mkdir -p semantic_layer/workspace/comics/3_explores
mkdir -p semantic_layer/workspace/jaffle_shop/1_raw_views
mkdir -p semantic_layer/workspace/jaffle_shop/2_refinements
mkdir -p semantic_layer/workspace/jaffle_shop/3_explores
```

Target layout:

```text
analytics-engineering/
├── malloy-config.json                 # VS Code / Malloy tooling connection
└── semantic_layer/
    ├── README.md
    ├── publisher.config.json          # local Publisher only
    └── workspace/
        ├── comics/
        │   ├── publisher.json
        │   ├── 1_raw_views/
        │   │   └── config.malloy
        │   ├── 2_refinements/
        │   │   ├── comics.malloy
        │   │   └── calendar.malloy
        │   └── 3_explores/
        │       └── comics_explore.malloy
        └── jaffle_shop/
            ├── publisher.json
            ├── 1_raw_views/
            │   └── config.malloy
            ├── 2_refinements/
            │   ├── customers.malloy
            │   ├── locations.malloy
            │   ├── order_items.malloy
            │   ├── orders.malloy
            │   ├── products.malloy
            │   └── supplies.malloy
            └── 3_explores/
                └── cafe_explore.malloy
```

The directory name is `workspace/`, not `packages/`, so it matches the
reference Publisher layout. The publishable package root is
`semantic_layer/workspace/<package>/`, the directory containing
`publisher.json`. `semantic_layer/publisher.config.json` is **not** uploaded to
Credible.

### 2.2 Add `publisher.json`

`semantic_layer/workspace/comics/publisher.json`:

```json
{
  "name": "comics",
  "version": "0.1.0",
  "description": "Layered XKCD comics and calendar semantic package over data_warehouse_demo.marts",
  "explores": [
    "3_explores/comics_explore.malloy"
  ]
}
```

`semantic_layer/workspace/jaffle_shop/publisher.json`:

```json
{
  "name": "jaffle_shop",
  "version": "0.1.0",
  "description": "Layered Jaffle Shop cafe semantic package over data_warehouse_demo.marts",
  "explores": [
    "3_explores/cafe_explore.malloy"
  ]
}
```

Rules:

- `name` and `version` are required by `cred publish`.
- `explores` is the Publisher allowlist for the published query surface. A
  `.malloy` file not listed there is not exposed as an explore.
- A published version is immutable. The workflow bumps the patch version on every change.
- Use lowercase package names to avoid URL and CLI ambiguity.
- Keep the folder name `jaffle_shop`; if Credible rejects the underscore in `name`, use `jaffle-shop` as the package name while keeping the folder unchanged.

### 2.3 Add Malloy sources

Use the same three-layer structure as the reference
`workspace/thelook_ecommerce` package. Do not add an `index.malloy`; Publisher
loads the explore file listed in `publisher.json`.

Layer 1 is the only place that touches physical table names.
`semantic_layer/workspace/comics/1_raw_views/config.malloy`:

```malloy
/// COMICS
source: comics_raw is motherduck.table('marts.comics')

/// CALENDAR
source: calendar_raw is motherduck.table('marts.calendar')
```

`semantic_layer/workspace/jaffle_shop/1_raw_views/config.malloy`:

```malloy
/// CUSTOMERS
source: cafe_customers_raw is motherduck.table('marts.cafe_customers')

/// LOCATIONS
source: cafe_locations_raw is motherduck.table('marts.cafe_locations')

/// ORDER ITEMS
source: cafe_order_items_raw is motherduck.table('marts.cafe_order_items')

/// ORDERS
source: cafe_orders_raw is motherduck.table('marts.cafe_orders')

/// PRODUCTS
source: cafe_products_raw is motherduck.table('marts.cafe_products')

/// SUPPLIES
source: cafe_supplies_raw is motherduck.table('marts.cafe_supplies')
```

Layer 2 refines each raw source independently. Every file imports
`../1_raw_views/config.malloy`, sets a `primary_key`, renames fields to the
published names, and adds documented dimensions and measures. Examples:

```malloy
import '../1_raw_views/config.malloy'

#(doc) "XKCD comic catalogue with publication metadata and text metrics."
source: comics is comics_raw extend {
  primary_key: Comic_key
  rename:
    `Comic_key` is `_key_comics`
    `Month` is `month`
    `Year` is `year`
  measure:
    `Comic_Count` is count()
}
```

```malloy
import '../1_raw_views/config.malloy'
import 'customers.malloy'
import 'locations.malloy'
import 'order_items.malloy'

#(doc) "One row per Jaffle Shop order."
source: cafe_orders is cafe_orders_raw extend {
  primary_key: Order_id
  join_one: cafe_customers on Customer_id = cafe_customers.Customer_id
  join_one: cafe_locations on Location_id = cafe_locations.Location_id
  join_many: cafe_order_items on Order_id = cafe_order_items.Order_id
  measure:
    `Order_Count` is count()
    `Total_Revenue` is sum(Order_total)
}
```

The full refinement set is:

- `comics/2_refinements/comics.malloy`
- `comics/2_refinements/calendar.malloy`
- `jaffle_shop/2_refinements/customers.malloy`
- `jaffle_shop/2_refinements/locations.malloy`
- `jaffle_shop/2_refinements/order_items.malloy`
- `jaffle_shop/2_refinements/orders.malloy`
- `jaffle_shop/2_refinements/products.malloy`
- `jaffle_shop/2_refinements/supplies.malloy`

Layer 3 is the published query surface. It imports refinements, defines the
top-level explore, and may join or `compose` sources:

```malloy
##! experimental.access_modifiers
import '../2_refinements/comics.malloy'
import '../2_refinements/calendar.malloy'

#(doc) "Publication-ready explore for XKCD comics enriched with calendar attributes."
source: comics_explore is comics extend {
  join_one: calendar on Calendar_key = calendar._key_calendar
  dimension:
    `Calendar_Year` is calendar.Calendar_year
} include {
  * private: calendar
}
```

```malloy
##! experimental.access_modifiers
import '../2_refinements/orders.malloy'

#(doc) "Order-grain explore for Jaffle Shop revenue and customer analysis."
source: cafe_explore is cafe_orders extend {
  dimension:
    `Customer_Name` is cafe_customers.Customer_name
    `Customer_Type` is cafe_customers.Customer_type
} include {
  * private: cafe_customers, cafe_locations
}
```

The first source definition is intentionally minimal. Add joins, dimensions, measures, and descriptions only after the package compiles and queries against MotherDuck.

### 2.4 Add the Malloy and Publisher configurations

`malloy-config.json` at the repository root is the connection configuration used
by the VS Code Malloy extension and other Malloy tooling. It defines a
connection named `motherduck`, matching the name used in every `.malloy` source:

```json
{
  "connections": {
    "motherduck": {
      "is": "duckdb",
      "databasePath": "md:data_warehouse_demo",
      "motherDuckToken": {
        "env": "MOTHERDUCK_TOKEN"
      },
      "workingDirectory": "semantic_layer/workspace"
    }
  }
}
```

`semantic_layer/publisher.config.json` is the local Publisher configuration:

```json
{
  "frozenConfig": false,
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
        { "name": "comics", "location": "./workspace/comics" },
        { "name": "jaffle_shop", "location": "./workspace/jaffle_shop" }
      ]
    }
  ]
}
```

`malloy-config.json` is for developer tooling. `publisher.config.json` is for
local Publisher only. Credible stores its own MotherDuck connection.

### 2.5 Add the semantic-layer README

Create `semantic_layer/README.md` with:

- The `workspace/` layout and the three-layer model.
- The difference between root `malloy-config.json` and local
  `semantic_layer/publisher.config.json`.
- The MotherDuck dependency and the required `data_warehouse_demo.marts` tables.
- Local Publisher command.
- Credible CI/CD publishing rule.
- The “no cross-repository symlink” rule.
- The statement that a package is owned by either CI/CD or git-backed modeling, never both.

### 2.6 Validate locally

Load the MotherDuck token:

```bash
cd /home/maxantipev/analytics-engineering/semantic_layer
set -a
source ../.env
set +a

npx --yes @malloy-publisher/server@0.0.244 \
  --server_root . \
  --config ./publisher.config.json \
  --port 4000 \
  --init
```

Open `http://localhost:4000` and confirm:

- [ ] Both `comics` and `jaffle_shop` are listed.
- [ ] The Publisher log has no `loadErrors`.
- [ ] A query against `comics_explore` returns rows.
- [ ] A query against `cafe_explore` returns rows.
- [ ] The package root is each directory under `workspace/`, not `semantic_layer/`.
- [ ] The root `malloy-config.json` resolves the `motherduck` connection and can
      read `marts.comics`.

Stop the server with `Ctrl+C`.

### 2.7 Dry-run the Credible upload

The dry run needs no Credible login and lists the files that would be uploaded:

`--dry-run` requires `cred-cli` `0.0.104` or later. The earlier `0.0.102`
release rejects it as an unknown option.

```bash
cd /home/maxantipev/analytics-engineering/semantic_layer/workspace/comics
cred publish --dry-run

cd ../jaffle_shop
cred publish --dry-run
```

Confirm:

- [ ] `publisher.json` is included.
- [ ] `1_raw_views/config.malloy`, all `2_refinements/*.malloy`, and the
      `3_explores/*.malloy` allowlisted explore are included.
- [ ] `.env`, `.git`, `node_modules`, and Publisher state are excluded.
- [ ] No file exceeds the package limit (50 MiB total).

Do **not** run a real `cred publish` from the laptop if CI/CD will own these packages. A manual publish consumes the current version, and the workflow would then need a higher version to publish again.

### 2.8 Commit the package source

```bash
cd /home/maxantipev/analytics-engineering
git add malloy-config.json semantic_layer
git status --short
git commit -m "feat(semantic): add layered comics and jaffle_shop Malloy packages"
```

Do not push yet if Phase 5 will add the workflow in the same change. A push now is harmless only if the workflow is not yet enabled.

### 2.9 Phase 1 verification checklist

- [x] `semantic_layer/workspace/comics/publisher.json` exists and has `name` + `version`.
- [x] `semantic_layer/workspace/jaffle_shop/publisher.json` exists and has `name` + `version`.
- [x] Each package uses `1_raw_views/config.malloy`, `2_refinements/`, and
      `3_explores/`; the `publisher.json` `explores` entry points at the
      layer-3 explore.
- [x] Root `malloy-config.json` defines the `motherduck` connection and resolves
      `marts.comics`.
- [x] Local Publisher lists both packages with no load errors.
- [x] Both explores return rows from MotherDuck.
- [x] `cred publish --dry-run` includes the expected files and excludes secrets.
- [x] Nothing is published to Credible yet.

### 2.10 Execution evidence — 2026-10-20

Re-executed on 2026-10-20 after the layout correction.

- Replaced `semantic_layer/packages/` with `semantic_layer/workspace/`. Each
  package now follows the reference three-layer structure:
  `1_raw_views/config.malloy`, `2_refinements/*.malloy`, and
  `3_explores/*.malloy`.
- Added repository-root `malloy-config.json` with a `motherduck` connection of
  type `duckdb`, `databasePath: md:data_warehouse_demo`, and
  `motherDuckToken: { "env": "MOTHERDUCK_TOKEN" }`.
- Updated `semantic_layer/publisher.config.json` to load
  `./workspace/comics` and `./workspace/jaffle_shop`.
- JSON syntax checks passed for root `malloy-config.json`, both `publisher.json`
  files, and the local Publisher configuration.
- Malloy tooling validation: `MalloyConfig` parsed `malloy-config.json` with no
  config log messages, resolved connection `motherduck`, and returned
  `marts.comics` count `3312`.
- Started Malloy Publisher `0.0.244` with `--init`. The readiness line reported
  `environments=1 packages=2 load_errors=0`.
- The Publisher model listing exposes only the allowlisted layer-3 files:
  `3_explores/comics_explore.malloy` and `3_explores/cafe_explore.malloy`.
- Queried through the Publisher API:
  `comics_explore` returned `Comic_Count = 3312`; grouping by `Calendar_Year`
  returned rows from 2006 through 2026.
- `cafe_explore` returned `Order_Count = 686` and `Total_Revenue = 6867.34`.
  Grouping by `Customer_Type` returned `returning = 676` orders and `new = 10`
  orders; grouping by `Location_Name` returned `Philadelphia`.
- `cred publish --dry-run --json` for `comics` included
  `1_raw_views/config.malloy`, both `2_refinements/*.malloy` files,
  `3_explores/comics_explore.malloy`, and `publisher.json`; `excluded` was empty
  and the archive was 2,781 bytes.
- `cred publish --dry-run --json` for `jaffle_shop` included
  `1_raw_views/config.malloy`, all six `2_refinements/*.malloy` files,
  `3_explores/cafe_explore.malloy`, and `publisher.json`; `excluded` was empty
  and the archive was 5,363 bytes.
- No real publish was executed. Both dry runs exited `0` with
  `"dryRun": true`, and `cred ls package` still does not list `comics` or
  `jaffle_shop`.
- Local Publisher state (`publisher_data/`, `publisher.db*`, and `.mcp.json`) is
  generated during validation and is excluded by `.gitignore`.
- Committed the layered source as `a2702fd`
  (`feat(semantic): add layered comics and jaffle_shop Malloy packages`) and
  pushed it to `origin/main`, 27 files changed. The commit replaces the flat
  `71ff049` layout with `semantic_layer/workspace/` and adds root
  `malloy-config.json`.

### 2.11 Stop gate

**Decision:** `TASK-02` is complete. Proceed only when the user explicitly starts `TASK-03`.

---

## 3. Phase 2 — Connect MotherDuck to the `demo` environment

> **Tag:** `TASK-03` | **Type:** execution | **Status:** `DONE` | **Exit gate:** §3.4 | **Next:** `TASK-04`

### 3.1 Add the connection

Two paths are supported. The CLI path is reproducible and was used for this
run; the App path remains the fallback. Both validate the connection and leave
the token outside the repository.

#### CLI path (used)

`cred add connection --from-publisher-config` reads the same connection block
as the local Publisher, tests it from Credible, and creates it. Export the
local token for this command only:

```bash
cd /home/maxantipev/analytics-engineering
set -a && . ./.env && set +a

cred add connection \
  --from-publisher-config semantic_layer/publisher.config.json \
  --name motherduck \
  --yes
```

In `cred` `0.0.104`, `--include-tables` is ignored when
`--from-publisher-config` is used, so the connection may be created with
`excludeAllTables: true` and `indexingStatus: SKIPPED`. Set the scope in a
second step with a temporary file outside the repository:

```bash
cat >/tmp/motherduck-scope.json <<'JSON'
[
  {
    "name": "motherduck",
    "type": "motherduck",
    "includeTables": ["marts.*"],
    "excludeAllTables": false
  }
]
JSON

cred update connection /tmp/motherduck-scope.json --yes
rm /tmp/motherduck-scope.json
```

`marts.*` covers every source used by both packages:
`marts.comics`, `marts.calendar`, and all six `marts.cafe_*` tables.

#### App path

1. Open `https://maxantipev.admin.credibledata.com`.
2. Select environment **`demo`** under **Packages & Connections**.
3. In **Connections**, click **+ Add Connection**.
4. Choose **MotherDuck**.
5. Enter:
   - **Connection name:** `motherduck`
   - **Access token:** the MotherDuck token from the local `.env`
   - **Database:** `data_warehouse_demo` if the form asks for a default database.
6. Click **Test the connection**. Do not continue if the test fails.
7. Configure scope: include the `marts` schema, or `marts.*`.
8. Click **Update Connection** and wait for indexing to finish.

Connection names cannot contain spaces or hyphens. Use `motherduck`, not `mother-duck` or `mother duck`.

### 3.2 Verify the connection

`jq` is not installed in this environment, so use the standard library:

```bash
cred ls connection 2>/dev/null | python -c '
import json, sys
for c in json.load(sys.stdin)["connections"]:
    print(c["name"], c["type"], c["indexingStatus"],
          c.get("includeTables"), c.get("excludeAllTables"))
'
```

Expected:

```text
bq_demo bigquery INDEXED ['california_schools.*', ...] False
motherduck motherduck INDEXED ['marts.*'] False
```

Also confirm the old connection is still present:

```bash
cred ls connection 2>/dev/null | python -c '
import json, sys
print("\n".join(c["name"] for c in json.load(sys.stdin)["connections"]))
'
```

Expected:

```text
bq_demo
motherduck
```

### 3.3 Why `bq_demo` is not sufficient

The Malloy sources in Phase 1 explicitly call `motherduck.table(...)`. A package using that source cannot fall back to `bq_demo`. Publishing may compile against the wrong connection or fail at query time if `motherduck` is absent.

Do not rename the connection to `bq_demo`, and do not change the source prefix to `bigquery` unless the models are deliberately rewritten.

### 3.4 Phase 2 verification checklist

- [x] `motherduck` appears in `cred ls connection`.
- [x] The connection test succeeded from Credible: `reachable from Credible`.
- [x] Indexing status is `INDEXED`.
- [x] The scope is `marts.*` and covers all tables used by both packages.
- [x] `bq_demo` remains available and `INDEXED` for unrelated examples.
- [x] No credentials were written to the repository.

### 3.5 Execution evidence — 2026-10-20

- Ran `cred add connection --from-publisher-config
  semantic_layer/publisher.config.json --name motherduck --yes`. Credible
  reported `motherduck: reachable from Credible` and created the connection.
- In `cred` `0.0.104`, the `--include-tables 'marts.*'` flag was not applied by
  the `--from-publisher-config` path. The first read showed
  `includeTables: null`, `excludeAllTables: true`, and `indexingStatus: SKIPPED`.
- Ran `cred update connection /tmp/task03-motherduck-update.json --yes` with
  `includeTables: ["marts.*"]` and `excludeAllTables: false`. Credible tested
  the merged connection and saved it.
- `cred` version used for this task: `0.0.104`.
- Final `cred ls connection` state:
  `motherduck motherduck INDEXED ['marts.*'] False`.
- `bq_demo` remains `bigquery INDEXED` with its original include list.
- A direct MotherDuck metadata query returned all eight expected `marts`
  tables: `cafe_customers`, `cafe_locations`, `cafe_order_items`,
  `cafe_orders`, `cafe_products`, `cafe_supplies`, `calendar`, `comics`.
- No token or populated connection file was written to the repository. The
  scope-update file lived under `/tmp` and was removed after the update.

### 3.6 Stop gate

**Decision:** `TASK-03` is complete. Proceed only when the user explicitly
starts `TASK-04`.

---

## 4. Phase 3 — Create the CI/CD access token

> **Tag:** `TASK-04` | **Type:** execution | **Status:** `DONE` | **Exit gate:** §4.4 | **Next:** `TASK-05`

### 4.1 Create a dedicated group

Do not reuse a personal browser session or an admin token.

```bash
cred add group credible-ci -d "CI/CD publisher for analytics-engineering" -y
cred add permission group:credible-ci modeler --environment demo -y
```

Verify:

```bash
cred ls group
cred ls permissions --environment demo
```

The group needs **Modeler** access to `demo` so its token can publish packages. It does not need organization admin.

### 4.2 Create the group access token

Use `--json-output` and redirect stdout to a mode-`600` file so the token is
never printed to the terminal or copied into shell history:

```bash
umask 077
cred add group-access-token credible-ci \
  github-actions-analytics-engineering \
  --json-output > /tmp/cred-group-token.json
chmod 600 /tmp/cred-group-token.json
```

The token is returned once in the `jwtToken` field. Store it directly in the
GitHub secret `CRED_JWT` in `antipev/analytics-engineering`, and optionally in
the gitignored local `.env`. Do not commit it.

- Omitting `--expires-at` uses Credible's 99-year default. The current token
  expires on `2125-10-20T20:36:35.752Z`, which is effectively non-expiring for
  this project. Credible does not expose a permanent no-expiry option.
- Rotating means creating a new token, updating `CRED_JWT`, and deleting the old token:

```bash
cred ls group-access-token credible-ci
cred rm group-access-token credible-ci <old-token-name> -y
```

### 4.3 Verify the token before wiring GitHub

Verify the token in a throwaway `HOME` so the local browser session in `~/.cred`
is not replaced:

```bash
set -a
source .env
set +a
CRED_TMP_HOME=$(mktemp -d)
HOME="$CRED_TMP_HOME" cred set-access-token "$CRED_JWT" -o maxantipev
HOME="$CRED_TMP_HOME" cred set environment demo
HOME="$CRED_TMP_HOME" cred status --json
rm -rf "$CRED_TMP_HOME"
```

Expected: organization `maxantipev`, environment `demo`, and
`"token": {"valid": true, "kind": "service-account"}`.

Do not run `cred publish` as part of this verification. The token's first real publish happens in GitHub Actions.

### 4.4 Phase 3 verification checklist

- [x] Group `credible-ci` exists.
- [x] The group has `modeler` permission on environment `demo`.
- [x] Token `github-actions-analytics-engineering` exists and expires on `2125-10-20T20:36:35.752Z`.
- [x] The token value is stored in the GitHub secret `CRED_JWT` and the gitignored local `.env`, and nowhere in version control.
- [x] `CRED_ORG=maxantipev` and `CRED_ENV=demo` are confirmed.
- [x] The local CLI can authenticate with the token and select `demo`.

### 4.5 Execution evidence — 2026-10-20

- Created group `credible-ci` in organization `maxantipev` and granted it
  `modeler` on environment `demo`.
- Created the token with `--json-output`; the value was written only to
  mode-`600` temporary files, copied into the GitHub secret `CRED_JWT`, and
  added to the gitignored `.env` as `CRED_JWT`, `CRED_ORG=maxantipev`, and
  `CRED_ENV=demo`.
- The token was rotated twice during verification: the initial token was
  briefly exposed and revoked, then a short-expiry replacement was replaced by
  the final token. The final token is `github-actions-analytics-engineering`
  with `expiresAt: 2125-10-20T20:36:35.752Z` and `expired: false`.
- Verified the final token with a throwaway `HOME`: `cred status --json`
  returned `"valid": true`, `"kind": "service-account"`, organization
  `maxantipev`, environment `demo`. `cred ls packages` returned the five
  existing `demo` packages.
- `git check-ignore -v .env` confirms `.env` is ignored; `.env` is mode `600`.
  No credential was written to the repository or committed.
- `antipev/analytics-malloy-credible` is not linked to Credible by this task.
  The environment still reports `gitModelingEnabled: false`; repository
  enrollment remains optional `TASK-08`.

### 4.6 Stop gate

**Decision:** `TASK-04` is complete. Proceed only when the user explicitly
starts `TASK-05`.

---

## 5. Phase 4 — Configure the GitHub App, secrets, variables, and `main` ruleset

> **Tag:** `TASK-05` | **Type:** execution | **Status:** `DONE` | **Exit gate:** §5.6 | **Next:** `TASK-06`
>
> **Result:** The App is created and installed on only `antipev/analytics-engineering` (installation ID `173548695`). All three repository secrets and all three variables are set. GitHub's classic branch protection rejects an App bypass on a user-owned repository, so `main` is protected by the active `main-protection` ruleset (ID `25509419`) with the App as an `always` bypass actor; classic branch protection was removed to avoid overriding that bypass. Verification is in §5.5.1–§5.5.2.

### 5.1 Create the CI/CD bot GitHub App

This App is **not** the Credible git-backed modeling App. It exists only so the workflow can commit the version bump back to `main` and bypass branch protection for that commit.

> **Why this App is required — do not replace it with `GITHUB_TOKEN` or a PAT.**
>
> The template's bump job pushes the version-bump commit directly to `main`. §5.4 protects `main` with a required pull request, so that push must come from an actor explicitly allowed to bypass the pull-request requirement. The App is that actor.
>
> - `GITHUB_TOKEN` is repository-scoped and ephemeral, but pushes made with it are still subject to branch protection. It cannot be selected as a pull-request bypass actor.
> - A fine-grained PAT can push only if its owner is allowed to bypass; it ties CI to a person, has account-level scope, and expires. A deploy key cannot be a pull-request bypass actor.
> - A GitHub App can be installed on exactly this repository, granted only Contents R/W, Pull requests R/W, Metadata R, and Environments R, audited, and rotated without changing a person's credentials. It is the least-privilege implementation of the template's contract.
> - This App does not connect Credible to the repository; that is the separate, optional git-backed modeling App in `TASK-08`.

If the App cannot be created, stop `TASK-05` as `BLOCKED`. Do not silently remove the pull-request requirement or substitute a PAT. Any fallback changes §5.4 and §6 and must be recorded as a deliberate reduction in protection.

| Alternative | What would change | Verdict |
| :--- | :--- | :--- |
| `GITHUB_TOKEN` with a direct push | The push is rejected by protected `main`; making it work requires removing the requirement that blocks it. | Rejected. It defeats the protection this task is meant to preserve. |
| Fine-grained PAT stored as a secret | Works only if the PAT owner may bypass protection; ties CI to a person, broadens scope, and expires. | Fallback only, with a recorded risk acceptance and a rotation owner. |
| Bump job opens a pull request and auto-merges | Requires redesigning the template's bump workflow and a second approval or auto-merge path. | Possible future redesign; outside `TASK-05`. |
| Disable branch protection | Publishing succeeds, but the review gate disappears. | Rejected. |

The manifest/localhost helper is only a convenience. Creating the App directly in the GitHub UI is equivalent and does not require port forwarding, so the UI path is the canonical procedure.

1. Open the account or organization settings:
   - User: **Settings → Developer settings → GitHub Apps**
   - Organization: **Settings → Developer settings → GitHub Apps**
2. Click **New GitHub App**.
3. Set:
   - **Name:** `credible-analytics-eng-cicd` (27 characters; GitHub App names are global and limited to 34 characters). If that name is taken, use `credible-analytics-cicd` (23 characters).
   - **Homepage URL:** `https://github.com/antipev/analytics-engineering`.
   - **Webhook:** uncheck **Active** and leave **Webhook URL** empty. If GitHub reports that a webhook URL is required, **Active** is still checked; clear the field and uncheck it again.
4. Repository permissions:
   - **Contents:** Read and write
   - **Pull requests:** Read and write
   - **Metadata:** Read (mandatory)
   - **Environments:** Read
5. Installation: **Only on this account**.
6. Click **Create GitHub App**.
7. Record the **App ID**.
8. Under **Private keys**, click **Generate a private key** and save the `.pem` file outside the repository.
9. Click **Install App**, choose **Only select repositories**, and select `antipev/analytics-engineering`. Do not choose **All repositories**.

Record the **App ID**, **App slug**, and **installation ID** for the §5.5 evidence table. The numeric App ID is required in the ruleset `bypass_actors` payload; the slug is only the identifier in the App settings URL. Do not guess either from the display name.

#### 5.1.1 Manual UI creation checklist

Use this checklist when creating the App directly in the browser. It is the canonical path when the localhost manifest helper cannot be reached.

| Field | Recorded value |
| :--- | :--- |
| App name | `credible-analytics-eng-cicd` |
| Owner | `@antipev` |
| App ID | `5402661` |
| App slug | `credible-analytics-eng-cicd` (confirm from the App settings URL) |
| Client ID | `Iv23li3rTwzEUFzpHo5f` (identifier only; the workflow uses the App ID and private key, not the Client ID) |
| Homepage URL | `https://github.com/antipev/analytics-engineering` |
| Webhook | Inactive; no webhook URL or secret |
| Installation scope | Only `antipev/analytics-engineering`; confirmed `repository_selection=selected` and exactly one repository |
| Private key | Never recorded here; save it outside the repository, store it in `CICD_BOT_APP_PRIVATE_KEY`, then delete the local file. This run generated `credible-analytics-eng-cicd.2026-10-20.private-key.pem`, uploaded it, and deleted the local file after verification. |

- Open `https://github.com/settings/apps/new` while signed in as the account that owns `antipev/analytics-engineering`.
- **Name:** `credible-analytics-eng-cicd` (27 characters).
  GitHub App names are limited to 34 characters. If this name is taken, use `credible-analytics-cicd` (23 characters). The slug shown in the App URL is derived from the name; record the actual slug.
- **Homepage URL:** `https://github.com/antipev/analytics-engineering`.
- **Webhook:** leave **Active** unchecked and leave **Webhook URL** empty.
  This App has no webhook. The form can show a required-URL validation message while **Active** is checked; unchecking **Active** removes that requirement. If the form still refuses an empty URL, use `https://github.com/antipev/analytics-engineering` as an inert placeholder and keep **Active** unchecked; record the deviation.
- **Repository permissions:**
  - Contents: **Read and write**
  - Pull requests: **Read and write**
  - Metadata: **Read** (mandatory)
  - Environments: **Read**
- **Where can this GitHub App be installed?** **Only on this account**.
- Click **Create GitHub App**.
- Record the numeric **App ID** shown on the App settings page.
- Under **Private keys**, click **Generate a private key**. GitHub downloads the `.pem` once; it cannot be downloaded again.
- Save the file outside the repository, for example
  `/home/maxantipev/.config/credible-cicd-app/credible-analytics-eng-cicd.2026-10-20.private-key.pem`, then restrict it:
  ```bash
  chmod 600 /home/maxantipev/.config/credible-cicd-app/credible-analytics-eng-cicd.2026-10-20.private-key.pem
  ```
- Click **Install App**, choose **Only select repositories**, and select only `antipev/analytics-engineering`. Do not choose **All repositories**.
- Reply with the numeric **App ID**, the **App slug** from `https://github.com/settings/apps/<slug>`, and confirmation that the PEM is at the path above.

#### 5.1.2 Installation page controls

The **Danger zone** on the App installation page controls only the installation:

- **Suspend** temporarily blocks the App from accessing the repository and minting installation
  tokens. It is reversible and does not delete the App registration.
- **Uninstall** removes the installation, revokes its access, and makes existing installation
  tokens fail. The App registration, App ID, slug, and private keys remain under
  `https://github.com/settings/apps/credible-analytics-eng-cicd`.

Do not use either control during normal operation. To change repository access, use **Configure**
on the installation page. To rotate a private key, open the App settings, generate a new key,
update `CICD_BOT_APP_PRIVATE_KEY`, then delete the old key. A new key is required if the local PEM
is lost; GitHub cannot re-download an existing key.

The verification script in §5.5.2 is a local helper, not something GitHub creates. It can be saved
or recreated at any time. It needs the PEM only for the App JWT and installation-token checks;
`--skip-app-installation` checks the repository-side ruleset, secrets, and variables without it.

### 5.2 Add repository secrets

In `antipev/analytics-engineering`:

**Settings → Secrets and variables → Actions → New repository secret**

| Secret | Value |
| :--- | :--- |
| `CICD_BOT_APP_ID` | The GitHub App ID from §5.1 |
| `CICD_BOT_APP_PRIVATE_KEY` | The entire `.pem` file, including the `-----BEGIN` and `-----END` lines |
| `CRED_JWT` | The group access token from §4.2 |

Never commit the `.pem` or the JWT. The workflow passes them through GitHub's secret store only.

The official template names this secret `JWT_ACCESS_TOKEN`. This runbook uses the more explicit `CRED_JWT`, so §6.2 changes the template's one secret reference to match.

### 5.3 Add repository variables

**Settings → Secrets and variables → Actions → Variables**

| Variable | Value |
| :--- | :--- |
| `CRED_ORG` | `maxantipev` |
| `CRED_ENV` | `demo` |
| `SET_LATEST` | `true` (optional; the template defaults to true) |

Use variables, not secrets, for the organization and environment names. They are visible in workflow logs and are not credentials.

### 5.4 Configure `main` protection and the App bypass

GitHub's classic branch protection does **not** allow a GitHub App in
`bypass_pull_request_allowances` on a user-owned repository. The API returns
`422 Only organization repositories can have users and team restrictions`, and
the dedicated required-pull-request-reviews endpoint returns HTTP 500. Use a
repository ruleset instead. The ruleset is the single source of truth; do not
also keep a classic rule with a pull-request requirement, because it will still
block the App.

In the UI: **Settings → Rules → Rulesets → New branch ruleset**, then configure:

- **Target branches:** include the default branch (`main`).
- **Enforcement status:** **Active**.
- **Bypass list:** add the App `credible-analytics-eng-cicd` with **Always**, and add **Repository admin** with **Always**. The admin entry lets the sole maintainer push and merge their own pull request; it does not let them submit an approving review on it.
- **Require a pull request before merging:** 1 approval.
- **Block force pushes** and **Restrict deletions**.

Or create the same ruleset with the API:

```bash
cat > /tmp/credible-main-ruleset.json <<'JSON'
{
  "name": "main-protection",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": {
      "include": ["~DEFAULT_BRANCH"],
      "exclude": []
    }
  },
  "bypass_actors": [
    {
      "actor_id": 5402661,
      "actor_type": "Integration",
      "bypass_mode": "always"
    },
    {
      "actor_id": 5,
      "actor_type": "RepositoryRole",
      "bypass_mode": "always"
    }
  ],
  "rules": [
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 1,
        "dismiss_stale_reviews_on_push": false,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": false
      }
    },
    {
      "type": "deletion"
    },
    {
      "type": "non_fast_forward"
    }
  ]
}
JSON

gh api -X POST repos/antipev/analytics-engineering/rulesets \
  --input /tmp/credible-main-ruleset.json
```

The `pull_request` rule parameter is `dismiss_stale_reviews_on_push`, not
`dismiss_stale_reviews`. The API rejects the whole rule with
`Invalid property /rules/0: data matches no possible input` when the wrong key
is used. The `bypass_actors` entry uses the numeric **App ID**, not the slug:
`actor_type` is `Integration` and `bypass_mode` must be `always` for a direct
push to `main`.

Ruleset bypass actors are roles, teams, and Apps; GitHub does not accept an
individual user. `actor_type: RepositoryRole` with `actor_id: 5` is the
repository-admin role. It lets the admin push to `main` and merge a pull
request with `gh pr merge --admin`; it does not let the admin approve their own
pull request. The one-approval requirement still applies to every non-bypass
actor.

Then remove the classic rule so it cannot override the bypass:

```bash
gh api -X DELETE repos/antipev/analytics-engineering/branches/main/protection
```

The delete returns `204 No Content`; a later `GET` on the classic protection
endpoint returns 404. Verify the ruleset and the rules that apply to `main`:

```bash
gh api repos/antipev/analytics-engineering/rulesets
gh api repos/antipev/analytics-engineering/rules/branches/main
```

Why the bypass is required: the template's bump job pushes a commit directly
to `main`. Without the App bypass, the pull-request rule rejects that push and
the publish job never receives a bumped package.

If required status checks are added later, add a `required_status_checks` rule
to this ruleset (for example, the Credible compile check only when git-backed
modeling is enabled). Do **not** enable a linear-history rule that conflicts
with the team's merge policy. Do **not** use **Squash and merge** for package
pull requests; Credible's template detects changes by commit ranges and can
miss squashed package changes.

### 5.5 Verify the GitHub configuration

Using the GitHub CLI:

```bash
cd /home/maxantipev/analytics-engineering

gh secret list --repo antipev/analytics-engineering
gh api repos/antipev/analytics-engineering/actions/variables \
  --jq '.variables[] | {name, value}'
gh api repos/antipev/analytics-engineering \
  --jq '{allow_squash_merge, allow_merge_commit, allow_rebase_merge}'
gh api repos/antipev/analytics-engineering/rulesets \
  --jq '.[] | {id, name, enforcement}'
gh api repos/antipev/analytics-engineering/rules/branches/main
gh api repos/antipev/analytics-engineering/branches/main/protection
```

`gh variable list` is not available in the installed `gh` 2.4.0, so use the API form above. The ruleset detail includes
`bypass_actors`; the App must appear with `actor_type: Integration`, `actor_id: 5402661`, and
`bypass_mode: always`. If `bypass_actors` is empty or the App is absent, the bypass is not configured.
The final command is expected to return HTTP 404 after the classic rule is removed; a 200 response
means a classic rule still exists and can override the ruleset bypass.

Confirm:

- [x] `CICD_BOT_APP_ID`, `CICD_BOT_APP_PRIVATE_KEY`, and `CRED_JWT` are listed as secrets.
- [x] `CRED_ORG`, `CRED_ENV`, and optionally `SET_LATEST` are listed as variables.
- [x] The App is installed on exactly this repository.
- [x] The `main-protection` ruleset is active and the App can bypass its pull-request rule.
- [x] The repository-admin role is an always-bypass actor, so the sole maintainer can push and merge their own pull request with `--admin`.
- [x] Classic branch protection is absent; the ruleset is the single source of truth.
- [x] Squash merges are disabled for package pull requests.

The App installation itself is verified with an App JWT and an installation access token; a normal
user token cannot read the installation endpoint. The ruleset bypass list is the authoritative
repository-side check. §5.5.2 provides a script that performs all of these checks.

#### 5.5.1 Execution evidence (2026-10-20)

| Item | Observed |
| :--- | :--- |
| Repository variables | `CRED_ORG=maxantipev`, `CRED_ENV=demo`, `SET_LATEST=true` |
| Repository secret names | `CICD_BOT_APP_ID`, `CICD_BOT_APP_PRIVATE_KEY`, `CRED_JWT` |
| Merge settings | `allow_squash_merge=false`; merge commit and rebase merge enabled |
| `main` protection | Active `main-protection` ruleset ID `25509419`: one approving review, deletion blocked, non-fast-forward blocked; classic branch protection removed (GET returns HTTP 404) |
| App bypass | `bypass_actors`: `actor_id=5402661`, `actor_type=Integration`, `bypass_mode=always`; ruleset applies to `main` |
| Admin bypass | Added during `TASK-07`: `actor_id=5`, `actor_type=RepositoryRole`, `bypass_mode=always`; `current_user_can_bypass=always`. Normal `gh pr merge` still reports `BLOCKED`; `gh pr merge --admin --merge` succeeds. |
| GitHub App | Created: `credible-analytics-eng-cicd`, App ID `5402661`, slug `credible-analytics-eng-cicd`, owner `@antipev` |
| App installation | ID `173548695`; `repository_selection=selected`; installation access token HTTP 201; only `antipev/analytics-engineering` is installed |
| Private key | RSA key validated, uploaded to `CICD_BOT_APP_PRIVATE_KEY`, and the local PEM was deleted after verification |
| Verification | Full §5.5.2 run with the PEM exited `0`; the post-deletion `--skip-app-installation` run also exited `0`, covering secrets, variables, merge, ruleset, bypass, and branch scope |
| Verification (TASK-07) | Re-ran §5.5.2 with `--skip-app-installation` after adding the repository-admin bypass; exit `0`, including the new admin-bypass checks |
| Deviations | App created directly in the UI (the localhost manifest helper was not used); name shortened to `credible-analytics-eng-cicd` because GitHub limits App names to 34 characters; classic branch protection replaced by the `main-protection` ruleset because the classic bypass API rejects App actors on user-owned repositories |
#### 5.5.2 Verification script

Save this as `verify_credible_github_app.py` outside the repository, or run it from a temporary
directory. It reads the private key only to mint an App JWT and an installation token; it never
prints either credential. After the local PEM is deleted, pass `--skip-app-installation` to check
the repository-side configuration only. It requires `PyJWT` and an authenticated `gh` CLI.

```bash
python3 -m pip install PyJWT
CICD_BOT_APP_PEM=/path/to/private-key.pem \
  python3 verify_credible_github_app.py
```

```python
#!/usr/bin/env python3
"""Verify the Credible CI/CD GitHub App installation and main-branch ruleset.

Usage:
    CICD_BOT_APP_PEM=/path/to/private-key.pem \
        python3 verify_credible_github_app.py

The script never prints the private key. Use --skip-app-installation after
deleting the key to check only repository-side configuration.

Requires: PyJWT, an authenticated `gh` CLI, and the App installed on the repo.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import jwt

OWNER = "antipev"
REPO = "analytics-engineering"
APP_ID = 5402661
RULESET_NAME = "main-protection"
DEFAULT_PEM = (
    "/home/maxantipev/.config/credible-cicd-app/"
    "credible-analytics-eng-cicd.2026-10-20.private-key.pem"
)


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "GH_PAGER": "cat", "GH_PROMPT_DISABLED": "1"}
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def gh(path: str) -> subprocess.CompletedProcess[str]:
    return run(["gh", "api", path])


def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"{'PASS' if ok else 'FAIL'}: {label}" + (f" — {detail}" if detail else ""))
    return ok


def app_token(app_id: int, pem: Path) -> str:
    now = int(time.time())
    return jwt.encode(
        {"iat": now - 60, "exp": now + 600, "iss": str(app_id)},
        pem.read_text(),
        algorithm="RS256",
    )


def api_request(path: str, token: str, method: str = "GET") -> tuple[int, dict]:
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        method=method,
        data=b"{}" if method == "POST" else None,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "credible-verify",
            **({"Content-Type": "application/json"} if method == "POST" else {}),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode() or "{}")


def app_get(path: str, app_id: int, pem: Path) -> tuple[int, dict]:
    return api_request(path, app_token(app_id, pem))


def app_post(path: str, app_id: int, pem: Path) -> tuple[int, dict]:
    return api_request(path, app_token(app_id, pem), method="POST")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pem", default=os.environ.get("CICD_BOT_APP_PEM", DEFAULT_PEM))
    parser.add_argument("--skip-app-installation", action="store_true")
    args = parser.parse_args()

    ok = True

    if not args.skip_app_installation:
        pem = Path(args.pem)
        if not pem.is_file():
            print(f"FAIL: private key not found at {pem}")
            print("      Use --skip-app-installation to check only repository settings.")
            return 1

        status, installation = app_get(
            f"/repos/{OWNER}/{REPO}/installation", APP_ID, pem
        )
        ok &= check("App installation endpoint", status == 200, f"HTTP {status}")
        if status == 200:
            ok &= check(
                "App ID",
                installation.get("app_id") == APP_ID,
                str(installation.get("app_id")),
            )
            ok &= check(
                "Installation scope",
                installation.get("repository_selection") == "selected",
                str(installation.get("repository_selection")),
            )
            print(f"INFO: installation ID {installation.get('id')}")

        installation_id = installation.get("id") if status == 200 else None
        if installation_id is not None:
            status, access = app_post(
                f"/app/installations/{installation_id}/access_tokens", APP_ID, pem
            )
            ok &= check("Installation access token", status == 201, f"HTTP {status}")
            if status == 201:
                status, repositories = api_request(
                    "/installation/repositories", access["token"]
                )
                ok &= check(
                    "Installation repositories endpoint", status == 200, f"HTTP {status}"
                )
                if status == 200:
                    names = [
                        item["full_name"]
                        for item in repositories.get("repositories", [])
                    ]
                    expected = [f"{OWNER}/{REPO}"]
                    ok &= check(
                        "Installed on exactly the target repository",
                        names == expected,
                        f"{names}",
                    )

    secrets = run(["gh", "secret", "list", "--repo", f"{OWNER}/{REPO}"])
    ok &= check("gh secret list", secrets.returncode == 0, secrets.stderr.strip())
    secret_names = {
        line.split()[0]
        for line in secrets.stdout.splitlines()
        if line.strip() and not line.startswith("NAME")
    }
    required_secrets = {"CICD_BOT_APP_ID", "CICD_BOT_APP_PRIVATE_KEY", "CRED_JWT"}
    ok &= check(
        "Required repository secrets",
        required_secrets <= secret_names,
        f"missing={sorted(required_secrets - secret_names)}",
    )

    variables = gh(f"repos/{OWNER}/{REPO}/actions/variables")
    ok &= check("Repository variables endpoint", variables.returncode == 0, variables.stderr.strip())
    if variables.returncode == 0:
        values = {
            item["name"]: item["value"]
            for item in json.loads(variables.stdout).get("variables", [])
        }
        ok &= check("CRED_ORG", values.get("CRED_ORG") == "maxantipev", str(values.get("CRED_ORG")))
        ok &= check("CRED_ENV", values.get("CRED_ENV") == "demo", str(values.get("CRED_ENV")))
        ok &= check("SET_LATEST", values.get("SET_LATEST") == "true", str(values.get("SET_LATEST")))

    repo = gh(f"repos/{OWNER}/{REPO}")
    ok &= check("Repository endpoint", repo.returncode == 0, repo.stderr.strip())
    if repo.returncode == 0:
        body = json.loads(repo.stdout)
        ok &= check(
            "Squash merge disabled",
            body.get("allow_squash_merge") is False,
            str(body.get("allow_squash_merge")),
        )

    rulesets = gh(f"repos/{OWNER}/{REPO}/rulesets")
    ok &= check("Rulesets endpoint", rulesets.returncode == 0, rulesets.stderr.strip())
    ruleset = None
    if rulesets.returncode == 0:
        for item in json.loads(rulesets.stdout):
            if item.get("name") == RULESET_NAME:
                detail = gh(f"repos/{OWNER}/{REPO}/rulesets/{item['id']}")
                if detail.returncode == 0:
                    ruleset = json.loads(detail.stdout)
                break
    ok &= check(f"Ruleset {RULESET_NAME!r} exists", ruleset is not None)
    if ruleset is not None:
        ok &= check(
            "Ruleset active",
            ruleset.get("enforcement") == "active",
            str(ruleset.get("enforcement")),
        )
        includes = ruleset.get("conditions", {}).get("ref_name", {}).get("include", [])
        ok &= check("Ruleset targets default branch", "~DEFAULT_BRANCH" in includes, str(includes))
        bypass = [
            actor
            for actor in ruleset.get("bypass_actors", [])
            if actor.get("actor_type") == "Integration" and actor.get("actor_id") == APP_ID
        ]
        ok &= check("App is a ruleset bypass actor", bool(bypass), json.dumps(bypass))
        ok &= check(
            "App bypass mode is always",
            bool(bypass) and bypass[0].get("bypass_mode") == "always",
            str(bypass[0].get("bypass_mode") if bypass else None),
        )
        admin_bypass = [
            actor
            for actor in ruleset.get("bypass_actors", [])
            if actor.get("actor_type") == "RepositoryRole"
            and actor.get("actor_id") == 5
        ]
        ok &= check(
            "Repository admin is a ruleset bypass actor",
            bool(admin_bypass),
            json.dumps(admin_bypass),
        )
        ok &= check(
            "Repository admin bypass mode is always",
            bool(admin_bypass) and admin_bypass[0].get("bypass_mode") == "always",
            str(admin_bypass[0].get("bypass_mode") if admin_bypass else None),
        )
        rule_types = {rule.get("type") for rule in ruleset.get("rules", [])}
        required_rules = {"pull_request", "deletion", "non_fast_forward"}
        ok &= check(
            "Ruleset enforces PR, deletion, and non-fast-forward",
            required_rules <= rule_types,
            f"missing={sorted(required_rules - rule_types)}",
        )
        pr_rule = next(
            (
                rule
                for rule in ruleset.get("rules", [])
                if rule.get("type") == "pull_request"
            ),
            None,
        )
        pr_count = (
            pr_rule.get("parameters", {}).get("required_approving_review_count")
            if pr_rule
            else None
        )
        ok &= check("Pull request rule requires one approval", pr_count == 1, str(pr_count))

    branch_rules = gh(f"repos/{OWNER}/{REPO}/rules/branches/main")
    ok &= check("Branch rules endpoint", branch_rules.returncode == 0, branch_rules.stderr.strip())
    if branch_rules.returncode == 0:
        source_ids = {
            rule.get("ruleset_id")
            for rule in json.loads(branch_rules.stdout)
            if rule.get("ruleset_id") is not None
        }
        expected_id = ruleset.get("id") if ruleset else None
        ok &= check(
            "Ruleset applies to main",
            expected_id in source_ids,
            f"ruleset_id={expected_id} sources={sorted(source_ids)}",
        )

    classic = gh(f"repos/{OWNER}/{REPO}/branches/main/protection")
    ok &= check(
        "Classic branch protection absent",
        classic.returncode != 0 and "HTTP 404" in classic.stderr,
        "expected 404; ruleset is the single source of truth",
    )

    print(f"\n{'PASS' if ok else 'FAIL'}: Credible GitHub App verification")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
```

### 5.6 Phase 4 verification checklist

- [x] GitHub App exists with Contents R/W, Pull requests R/W, Metadata R, Environments R.
- [x] App installation is limited to `antipev/analytics-engineering` (installation ID `173548695`).
- [x] Private key is stored only in GitHub secrets; the local PEM was deleted.
- [x] `CRED_JWT` is stored only in GitHub secrets.
- [x] `CRED_ORG=maxantipev` and `CRED_ENV=demo`.
- [x] The active `main-protection` ruleset allows the App to push the version bump.
- [x] No secret has been written to the working tree.

---

## 6. Phase 5 — Install and adapt Credible's CI/CD template

> **Tag:** `TASK-06` | **Type:** execution | **Status:** `DONE` | **Exit gate:** §6.7 | **Next:** `TASK-07`
>
> **Result:** The three template workflows and three scripts were copied from commit `5e6b2be`; `deploy.yaml` watches `semantic_layer/workspace/**` and uses `CRED_JWT`; package detection and publish splitting target `semantic_layer/workspace/`. Static checks and local detection pass. Evidence is in §6.8.

### 6.1 Copy the official template files

Do **not** click “Use this template”. That creates a new repository; this project publishes from the existing `analytics-engineering` repository.

Copy the template into a temporary directory and bring over only the workflow and script files:

```bash
cd /home/maxantipev/analytics-engineering

TEMPLATE_DIR="$(mktemp -d)"
git clone --depth 1 \
  https://github.com/credibledata/credible-cicd-template.git \
  "$TEMPLATE_DIR"

mkdir -p .github/workflows scripts

cp "$TEMPLATE_DIR/.github/workflows/deploy.yaml" .github/workflows/
cp "$TEMPLATE_DIR/.github/workflows/bump-package-versions.yml" .github/workflows/
cp "$TEMPLATE_DIR/.github/workflows/publish-packages.yml" .github/workflows/

cp "$TEMPLATE_DIR/scripts/detect_changed_packages.py" scripts/
cp "$TEMPLATE_DIR/scripts/bump_versions.py" scripts/
cp "$TEMPLATE_DIR/scripts/cred_publish.sh" scripts/

chmod +x scripts/detect_changed_packages.py scripts/bump_versions.py scripts/cred_publish.sh
```

Review the copied files before committing. They are third-party automation with write access to `main` through the GitHub App. The template commit used for this execution is `5e6b2be` (2026-09-09).

### 6.2 Adapt the trigger path

The template watches `packages/**`. This repository stores packages under `semantic_layer/workspace/**`.

In `.github/workflows/deploy.yaml`, change:

```yaml
on:
  push:
    branches: [main]
    paths:
      - 'packages/**'
```

to:

```yaml
on:
  push:
    branches: [main]
    paths:
      - 'semantic_layer/workspace/**'
```

Then change the template's access-token secret reference:

```yaml
    secrets:
      jwt_access_token: ${{ secrets.JWT_ACCESS_TOKEN }}
```

to:

```yaml
    secrets:
      jwt_access_token: ${{ secrets.CRED_JWT }}
```

Leave the rest of `deploy.yaml` unchanged: `bump` calls `bump-package-versions.yml`, and `publish` calls `publish-packages.yml` with the bumped package list.

### 6.3 Adapt package detection

The template hard-codes `packages/` in `scripts/detect_changed_packages.py`. Change the default base directory:

```python
def is_safe_path(file_path: Path, base_dir: str = "packages") -> bool:
```

to:

```python
def is_safe_path(file_path: Path, base_dir: str = "semantic_layer/workspace") -> bool:
```

Change the changed-file filter in `main()`:

```python
for f in changed:
    if f.startswith("packages/"):
```

to:

```python
for f in changed:
    if f.startswith("semantic_layer/workspace/"):
```

`find_package_root()` must also change its boundary check from `packages` to
`workspace`:

```python
        # Stop if we've left the workspace directory
        if "workspace" not in current.parts:
            break
```

Do **not** globally replace the word `packages` in the script. Only the three
checks above define the repository-specific root.

### 6.4 Adapt the publish script's package split

`scripts/cred_publish.sh` splits multiple package entries on the literal string ` packages/`:

```bash
PACKAGES_ARRAY=$(echo "$PACKAGES" | sed 's/ packages\//\npackages\//g')
```

That no longer matches `semantic_layer/workspace/` after the first entry. Change it to:

```bash
PACKAGES_ARRAY=$(echo "$PACKAGES" | sed 's# semantic_layer/workspace/#\nsemantic_layer/workspace/#g')
```

`bump_versions.py` needs no change: it receives package directories as arguments and reads each `publisher.json`.

### 6.5 Validate the adapted scripts

Run static checks:

```bash
cd /home/maxantipev/analytics-engineering

python -m py_compile scripts/detect_changed_packages.py scripts/bump_versions.py
bash -n scripts/cred_publish.sh
```

Test detection against the last commit:

```bash
BASE="$(git rev-parse HEAD~1)"
HEAD="$(git rev-parse HEAD)"
python scripts/detect_changed_packages.py "$BASE" "$HEAD"
```

Expected when the last commit changed the packages:

```text
[detected] semantic_layer/workspace/comics/1_raw_views/config.malloy → package: semantic_layer/workspace/comics
...
TO_BUMP=semantic_layer/workspace/comics|||semantic_layer/workspace/jaffle_shop
ALREADY_BUMPED=
```

When the last commit did not touch a package, both output lists are empty and the workflow skips the bump.

### 6.6 Alternative: use a root `packages/` directory

If you are willing to move the packages to the repository root, the template works without the three path edits:

```text
analytics-engineering/
└── packages/
    ├── comics/
    └── jaffle_shop/
```

That layout also satisfies git-backed modeling's top-level-package rule. It is a valid choice, but it changes the repository organization described in the main report. Pick one layout and apply it consistently; do not maintain both copies.

### 6.7 Phase 5 verification checklist

- [x] `.github/workflows/deploy.yaml` exists and watches `semantic_layer/workspace/**`.
- [x] `deploy.yaml` passes `${{ secrets.CRED_JWT }}` as `jwt_access_token`.
- [x] `.github/workflows/bump-package-versions.yml` exists.
- [x] `.github/workflows/publish-packages.yml` exists.
- [x] `scripts/detect_changed_packages.py` uses `semantic_layer/workspace`.
- [x] `scripts/cred_publish.sh` splits on `semantic_layer/workspace/`.
- [x] `python -m py_compile` succeeds.
- [x] `bash -n scripts/cred_publish.sh` succeeds.
- [x] Local detection returns the expected package paths.
- [x] No secret or `.pem` file is staged.

### 6.8 Execution evidence (2026-10-20)

| Item | Observed |
| :--- | :--- |
| Template source | `credibledata/credible-cicd-template` at commit `5e6b2be` (2026-09-09) |
| Workflows | `.github/workflows/deploy.yaml`, `bump-package-versions.yml`, `publish-packages.yml` |
| Scripts | `scripts/detect_changed_packages.py`, `bump_versions.py`, `cred_publish.sh` (mode `755`) |
| Trigger | `deploy.yaml` watches `semantic_layer/workspace/**` on `main` |
| Credentials | `deploy.yaml` passes `${{ secrets.CRED_JWT }}` as `jwt_access_token`; App secrets are unchanged |
| Package detection | `is_safe_path` base and changed-file filter use `semantic_layer/workspace`; `find_package_root` stops at `workspace` |
| Publish split | `cred_publish.sh` splits on ` semantic_layer/workspace/`; examples and diagnostics use the same path |
| Static validation | `python -m py_compile` and `bash -n` pass; all three workflow YAML files parse with PyYAML |
| Local detection | `HEAD~1..HEAD` → `TO_BUMP=semantic_layer/workspace/comics|||semantic_layer/workspace/jaffle_shop`, `ALREADY_BUMPED=`; same-commit range is empty |
| Simulated bump | Temporary copies of both packages bumped `0.1.0` → `0.1.1`; repository `publisher.json` files were not modified |
| Repository state | New workflow and script files were untracked at the end of `TASK-06`; they were committed and merged in `TASK-07` (PR #1, merge commit `ffbd4a7`) |
| Secrets | No secret value or `.pem` was found in the new files |

---

## 7. Phase 6 — First publish and verification

> **Tag:** `TASK-07` | **Type:** execution | **Status:** `DONE` | **Exit gate:** §7.9 | **Next:** `TASK-09`

### 7.1 Review the complete change locally

```bash
cd /home/maxantipev/analytics-engineering

git status --short
git diff --stat
git diff -- .github/workflows scripts semantic_layer
```

Confirm the diff contains only:

- the semantic packages;
- the local Publisher config and README;
- the three workflow files;
- the three template scripts and the path adaptations.

It must not contain `.env`, a `.pem`, a token, or `workspace/semantic_layer/`.

> **Current-state trigger note:** The semantic packages are already committed on
> `main`. A pull request that contains only `.github/` and `scripts/` does not
> match `semantic_layer/workspace/**`, so `deploy.yaml` will not run. The
> `TASK-07` pull request therefore updated the `description` field in both
> `publisher.json` files to mention MotherDuck. That is a real package metadata
> change, so both package directories were detected and published. Do not rely
> on a CI-only pull request for the first publish.

### 7.2 Commit and open a pull request

Direct pushes to `main` are blocked by the `main-protection` ruleset configured in Phase 4. Use a feature branch and a **merge commit**:

```bash
git checkout -b feat/credible-semantic-ci
git add .github scripts semantic_layer
git commit -m "feat(ci): publish semantic layer packages to Credible"

git push -u origin feat/credible-semantic-ci
gh pr create \
  --title "Publish semantic layer packages to Credible" \
  --body "Adds comics and jaffle_shop packages plus the adapted Credible CI/CD workflow."
```

Merge with **Merge commit** or **Rebase and merge**, never **Squash and merge**.

If the pull request author is the only maintainer, GitHub cannot satisfy the
one-approval rule because an author cannot approve their own pull request. The
repository-admin bypass from §5.4 allows the administrator override:

```bash
gh pr merge 1 --admin --merge --delete-branch
```

Normal `gh pr merge` still reports `BLOCKED` with `REVIEW_REQUIRED`; the
`--admin` flag is required for the sole-maintainer case. For a pull request
authored by someone else, use the normal merge after the required approval.

### 7.3 Watch the workflow

```bash
gh run list --workflow deploy.yaml --limit 5
gh run watch
```

Expected sequence:

```text
Bump and Publish Packages
├── bump (Bump Package Versions)
│   ├── creates a GitHub App token
│   ├── checks out main with full history
│   ├── detects changed packages
│   ├── bumps 0.1.0 → 0.1.1 in each changed publisher.json
│   └── commits "chore: auto-bump package versions [skip ci]"
└── publish (Publish Packages)
    ├── installs @credibledata/cred-cli
    ├── cred set-access-token "$CRED_JWT" -o maxantipev
    ├── cred set environment demo
    ├── publishes each package with --set-latest
    └── exits non-zero if any package fails
```

The bump commit contains `[skip ci]`, so GitHub does not create a second workflow run. The `if` guard is a second layer of protection if the skip marker is ever removed.

Observed on 2026-10-20: run [`39508584228`](https://github.com/antipev/analytics-engineering/actions/runs/39508584228) completed with `conclusion: success`. The `bump` job took 12s and the `publish` job took 36s. The bot commit `e55b110` contains `[skip ci]`, so it did not create a second publish run.

### 7.4 Verify the package versions

```bash
cred status
cred get environment demo
cred ls package
cred get package comics
cred get package jaffle_shop
cred ls version comics
cred ls version jaffle_shop
```

Expected:

- Both package names appear in `cred ls package`.
- The latest version is `0.1.1` (or the next patch after the committed version).
- `cred get package` reports the latest version and whether new versions promote automatically.

Observed on 2026-10-20:

| Package | `latestVersion` | `indexStatus` | `autoPromote` | `warnings` |
| :--- | :--- | :--- | :--- | :--- |
| `comics` | `0.1.1` | `indexed` | `true` | `[]` |
| `jaffle_shop` | `0.1.1` | `indexed` | `true` | `[]` |

Check the build status of the published versions:

```bash
cred get version comics 0.1.1
cred get version jaffle_shop 0.1.1
```

Observed: both returned `buildStatus: READY`, `refusedSources: []`, `stale: false`, and a `promotedAt` timestamp.

Wait until:

```text
buildStatus: READY
```

`FAILED` means the package did not compile or a table/connection was unavailable. `UNSUPPORTED` means a persisted source uses a database that cannot be materialized; it is not automatically an error, but the package is queried live.

### 7.5 Verify in the Credible App

1. Open `https://maxantipev.admin.credibledata.com`.
2. Select environment **`demo`**.
3. Confirm `comics` and `jaffle_shop` appear under packages.
4. Open each package and run a simple query:
   - `comics` → select a few rows.
   - `jaffle_shop` → query `cafe_orders`.
5. Confirm the query uses the `motherduck` connection, not `bq_demo`.
6. Open the workspace page and confirm the package surfaces are available.

The website is served from the Credible environment, not from GitHub. A successful workflow only means the upload succeeded; indexing and materialization still have to finish before every surface shows the new version.

### 7.6 Verify the version-bump commit

```bash
git fetch origin
git log --oneline origin/main -5
```

Expected: the top commit is the bot commit, for example:

```text
chore: auto-bump package versions [skip ci]
```

Observed: `e55b110 chore: auto-bump package versions [skip ci]` is the top commit on `origin/main`; both `publisher.json` files contain `"version": "0.1.1"`.

Confirm both `publisher.json` files contain the new version:

```bash
git show origin/main:semantic_layer/workspace/comics/publisher.json
git show origin/main:semantic_layer/workspace/jaffle_shop/publisher.json
```

### 7.7 Failure handling

**`version already exists`**

A package was published manually or by an earlier run at the same version. The template skips it and continues. If the code changed after that publish, bump the version manually and push again:

```bash
# edit publisher.json to the next patch version
git add semantic_layer/workspace/<package>/publisher.json
git commit -m "chore(semantic): bump <package> version"
```

**`Failed to set access token`**

- `CRED_JWT` is missing, expired, or does not belong to `credible-ci`.
- Recreate the token and update the secret.

**`Failed to set environment: demo`**

- The token's group lacks `modeler` on `demo`.
- Confirm with `cred ls permissions --environment demo`.

**`Package directory does not exist`**

The path adaptation in Phase 5 is incomplete. Run the detection script locally and compare its output with the package paths.

**Compile failure**

- The Malloy source references a missing table or an unknown connection.
- Check the marts from §1.2 and the `motherduck` connection from Phase 2.
- Run the same package in the local Publisher to see the full compile error.

### 7.8 Rollback

Roll back by re-pinning the previous version; do not rewrite the workflow history:

```bash
cred update package comics --version 0.1.0
cred update package jaffle_shop --version 0.1.0
```

Then fix the source and publish a new patch. The old version remains available.

### 7.9 Phase 6 verification checklist

- [x] The pull request contains only intended files.
- [x] The workflow's `bump` job succeeds and pushes a bot commit.
- [x] The workflow's `publish` job succeeds for both packages.
- [x] `cred ls package` lists `comics` and `jaffle_shop`.
- [x] `cred get package` reports the expected latest version.
- [x] `cred get version` reaches `READY`.
- [x] Both packages compile and index successfully in Credible; the package pages are available at the URLs reported by `cred publish`.
- [x] The packages use the `motherduck` connection; `refusedSources` is empty and no `bq_demo` dependency was introduced.
- [x] The bot commit is present on `origin/main`.
- [x] The run did not publish the same version twice.

> The browser query spot-check in §7.5 remains available as a manual confirmation; the published versions are already `READY` and indexed.

### 7.10 Execution evidence (2026-10-20)

| Item | Observed |
| :--- | :--- |
| Pull request | [#1](https://github.com/antipev/analytics-engineering/pull/1) `Publish semantic layer packages to Credible`; merged with `gh pr merge 1 --admin --merge --delete-branch` |
| Trigger | Both `publisher.json` descriptions changed to include `MotherDuck`; the PR also added the three workflows and three scripts |
| Merge commit | `ffbd4a7` |
| Workflow run | [`39508584228`](https://github.com/antipev/analytics-engineering/actions/runs/39508584228), `Bump and Publish Packages`, `conclusion: success` |
| Detection | `TO_BUMP=semantic_layer/workspace/comics|||semantic_layer/workspace/jaffle_shop`, `ALREADY_BUMPED=` |
| Bump | `comics` and `jaffle_shop` `0.1.0` → `0.1.1`; bot commit `e55b110` |
| Publish | `comics@0.1.1` and `jaffle_shop@0.1.1`, both `--set-latest`; summary `Published: 2`, `Skipped: 0`, `Failed: 0` |
| Credible state | Both packages `latestVersion: 0.1.1`, `indexStatus: indexed`, `autoPromote: true`, `warnings: []`; both versions `buildStatus: READY`, `refusedSources: []` |
| Published URLs | `https://maxantipev.app.credibledata.com/demo/comics/0.1.1` and `https://maxantipev.app.credibledata.com/demo/jaffle_shop/0.1.1` |
| Loop prevention | The bot commit contains `[skip ci]`; no second publish run was created |
| Credible warning | `"explores" in publisher.json is deprecated`; current behavior is preserved and both packages still expose their intended source. Decision on 2026-10-21: keep `explores` for now and do **not** migrate to `index.malloy` as part of the current scope. The replacement changes the published package surface and must be validated in both Credible and Publisher before adoption. Documented in TASK-09a §9A.3. |
| Admin bypass | `main-protection` now has `actor_id=5`, `actor_type=RepositoryRole`, `bypass_mode=always`; the normal merge path still reports `BLOCKED`, so `--admin` is required |

### 7.11 Routine change workflow (admin merge)

Every subsequent change uses the same path. The full quick reference is
[`ADMIN_MERGE_QUICK_REFERENCE.md`](./ADMIN_MERGE_QUICK_REFERENCE.md); the short
version is:

```bash
git switch main && git pull --ff-only
git switch -c feat/<short-name>
# edit
git add <paths> && git commit -m "feat(semantic): <what changed>"
git push -u origin feat/<short-name>
gh pr create --base main --head feat/<short-name> \
  --title "<title>" --body "<what changed and why>"
gh pr merge <number> --admin --merge --delete-branch
git switch main && git pull --ff-only
gh run list --limit 3
```

Why the extra flag: the `main-protection` ruleset requires one approval, and
GitHub forbids approving your own pull request. The repository-admin role is an
always-bypass actor, so `--admin` merges the PR without an approval. It is a
ruleset override, not a review; the PR still shows no approving review. Do not
use `--squash`, and do not use `--admin` to merge a known failure. See
§5.4 for the ruleset details and §7.10 for the first verified run.

---

## 8. Phase 7 — Optional: git-backed modeling through a mirror repository

> **Tag:** `TASK-08` | **Type:** optional execution | **Status:** `SKIPPED` | **Exit gate:** §8.8 | **Skip:** allowed only on explicit instruction; not required for the end state.
>
> **Decision (2026-10-20):** Skipped on explicit instruction. `TASK-07` CI publishing remains the package owner; no repository is enrolled for git-backed modeling, so `cred publish` continues to work. See §8.0 for the ownership distinction.

Skip this phase unless the team needs analysts to edit models in the Credible App and publish by merging a pull request.

### 8.1 Why the current repository cannot be enrolled as-is

Git-backed modeling requires:

- **one repository per environment**;
- each package as a **top-level directory**;
- text files only (no binary or large files);
- a base branch with at least one commit.

The current repository has:

```text
semantic_layer/workspace/comics/
semantic_layer/workspace/jaffle_shop/
```

Credible would not see those as top-level packages. The two options are:

1. Move the packages to `comics/` and `jaffle_shop/` at the repository root. This changes the layout in the main report and makes CI/CD path adaptation unnecessary, but it consumes the repository root with package directories.
2. Mirror `semantic_layer/workspace/` into a dedicated repository whose root is exactly:

```text
semantic-layer/
├── comics/
└── jaffle_shop/
```

This runbook uses option 2 because it preserves the canonical layout and does not mix the Publisher repository with the Credible repository.

### 8.2 Create the mirror repository

Create a **private** repository with an initial commit:

```bash
gh repo create antipev/semantic-layer \
  --private \
  --add-readme \
  --description "Credible git-backed mirror of analytics-engineering/semantic_layer/workspace"
```

Confirm the default branch is `main`.

Create a fine-grained personal access token (or a deploy key) with access to **only** `antipev/semantic-layer`:

- **Contents:** Read and write
- **Pull requests:** Read and write
- **Metadata:** Read

Store it in `antipev/analytics-engineering` as the secret `SEMANTIC_LAYER_MIRROR_TOKEN`. The repository's own `GITHUB_TOKEN` cannot write to a different repository.

This runbook mirrors files with `rsync` so each pull request has a clean commit on the mirror's `main`. The `git subtree split --prefix=semantic_layer/workspace` approach in report §13.4 is an alternative that preserves source history, but its first merge into a repository with an existing `main` can require unrelated-history handling. The file mirror avoids that failure mode.

### 8.3 Add the mirror workflow

Create `.github/workflows/mirror-semantic-layer.yml` in `analytics-engineering`:

```yaml
name: Mirror semantic layer

on:
  push:
    branches: [main]
    paths:
      - 'semantic_layer/workspace/**'
  workflow_dispatch:

permissions:
  contents: read

jobs:
  mirror:
    runs-on: ubuntu-latest

    steps:
      - name: Check out analytics-engineering
        uses: actions/checkout@v4
        with:
          path: source
          fetch-depth: 0

      - name: Check out mirror repository
        uses: actions/checkout@v4
        with:
          repository: antipev/semantic-layer
          token: ${{ secrets.SEMANTIC_LAYER_MIRROR_TOKEN }}
          path: mirror
          fetch-depth: 0

      - name: Copy packages to mirror root
        run: |
          set -Eeuo pipefail

          for package in comics jaffle_shop; do
            mkdir -p "mirror/${package}"
            rsync -a --delete \
              "source/semantic_layer/workspace/${package}/" \
              "mirror/${package}/"
          done

      - name: Open synchronization pull request
        env:
          GH_TOKEN: ${{ secrets.SEMANTIC_LAYER_MIRROR_TOKEN }}
          SOURCE_SHA: ${{ github.sha }}
        run: |
          set -Eeuo pipefail

          cd mirror

          if [ -z "$(git status --porcelain)" ]; then
            echo "Mirror already up to date"
            exit 0
          fi

          BRANCH="sync/${SOURCE_SHA::12}"

          git config user.name "semantic-layer-mirror[bot]"
          git config user.email "semantic-layer-mirror@users.noreply.github.com"
          git checkout -B "$BRANCH"
          git add comics jaffle_shop
          git commit -m "sync: ${SOURCE_SHA}"
          git push --force origin "$BRANCH"

          gh pr create \
            --repo antipev/semantic-layer \
            --base main \
            --head "$BRANCH" \
            --title "Sync semantic layer ${SOURCE_SHA::12}" \
            --body "Mirror of antipev/analytics-engineering at ${SOURCE_SHA}." \
            || gh pr list --repo antipev/semantic-layer --head "$BRANCH"
```

The workflow opens a pull request; it does not merge it. A person reviews and merges, and Credible publishes the merged version.

Why a pull request instead of a direct push: the documented git-backed lifecycle publishes on **merge**. A direct push to `main` may update the repository without producing a published version. Use the PR path unless Credible support explicitly confirms that direct pushes publish.

### 8.4 Merge the initial mirror pull request

Run the workflow once:

```bash
gh workflow run mirror-semantic-layer.yml --repo antipev/analytics-engineering
gh run list --workflow mirror-semantic-layer.yml --limit 3
```

Open the resulting pull request in `antipev/semantic-layer`, review the root layout, and merge it. This seeds the mirror with `comics/` and `jaffle_shop/` at the root **before** Credible enrollment.

Verify the mirror:

```bash
gh repo clone antipev/semantic-layer /tmp/semantic-layer-check
find /tmp/semantic-layer-check -maxdepth 2 -name publisher.json -print
```

Expected:

```text
/tmp/semantic-layer-check/comics/publisher.json
/tmp/semantic-layer-check/jaffle_shop/publisher.json
```

Do not edit the mirror directly. The next synchronization overwrites package files.

### 8.5 Enroll the mirror in Credible

Enrollment is support-assisted. Creating the repository and installing the App are not enough.

1. Contact Credible support or the account team and provide:
   - repository owner: `antipev`
   - repository name: `semantic-layer`
   - base branch: `main`
   - environment: `demo`
2. Install the **Credible GitHub App** on `antipev/semantic-layer`:
   - **Only select repositories**
   - **Contents:** Read and write
   - **Pull requests:** Read and write
   - **Checks:** Write
   - **Metadata:** Read
3. Wait for Credible to confirm that the repository is registered to `demo`.
4. In the Credible App:
   - open the `demo` environment;
   - click **Manage environment**;
   - turn on **Git-backed modeling**;
   - enter owner `antipev`, repository `semantic-layer`, base branch `main`;
   - save.

The CLI equivalent, only after Credible confirms registration, is:

```bash
cred update environment demo \
  --git-modeling true \
  --git-repository-owner antipev \
  --git-repository-name semantic-layer \
  --git-base-branch main \
  -y
```

If this fails because the repository is not registered, stop and return to support. Do not try to bypass the registration step by editing fields locally.

### 8.6 Verify git-backed modeling

```bash
cred get environment demo
```

Expected fields:

```json
{
  "gitModelingEnabled": true,
  "gitRepositoryOwner": "antipev",
  "gitRepositoryName": "semantic-layer",
  "gitBaseBranch": "main",
  "gitRepositoryRegistered": true
}
```

Then test the full loop:

1. Open the `demo` environment in Credible.
2. Start a draft for `comics`.
3. Ask for a harmless change, such as a description or a view.
4. Confirm Credible opens a branch and pull request in `antipev/semantic-layer`.
5. Review the diff and merge the pull request with a merge commit.
6. Confirm a new package version appears in Credible.
7. Confirm `cred get version` reaches `READY`.

Also test the ownership guard:

```bash
cd semantic_layer/workspace/comics
cred publish --dry-run
```

A dry run only lists files and is safe. After the package is owned by git-backed modeling, a real `cred publish` or CI upload to it should be refused with an error such as `GIT_BACKED_PACKAGE_REQUIRES_DRAFT`. That refusal is expected, not a bug.

### 8.7 What happens to the CI/CD workflow

The two paths coexist per package, but not for the same package:

- A package published only by CI/CD remains CI/CD-owned until it is first edited in the Credible App.
- The first in-app edit makes that package git-backed. From then on, merging its pull request is the only way to publish it.
- The other package can remain CI/CD-owned.
- If both packages become git-backed, disable the CI publish workflow for them, or leave it in place and accept that its uploads are refused. Prefer disabling the workflow to avoid noisy failures.

Do not assume that un-enrolling the environment converts already git-backed packages back to CI ownership. Confirm that behavior with Credible support before changing ownership.

### 8.8 Phase 7 verification checklist

- [ ] Mirror repository is private and has `main`.
- [ ] `comics/` and `jaffle_shop/` are at the mirror root.
- [ ] Initial mirror pull request was merged before enrollment.
- [ ] Credible GitHub App is installed only on the mirror repository.
- [ ] Credible support has registered the repository to `demo`.
- [ ] **Manage environment** shows Git-backed modeling enabled.
- [ ] `gitRepositoryRegistered` is `true`.
- [ ] An in-app draft produces a pull request.
- [ ] Merging that pull request publishes a new version.
- [ ] A direct `cred publish` is refused for the git-backed package.
- [ ] The team has recorded which package is CI-owned and which is git-backed.

---

## 9. Phase 8 — Synchronise the Malloy Publisher workspace

> **Tag:** `TASK-09` | **Type:** execution | **Status:** `DONE` | **Exit gate:** §9.9 | **Next:** `GATE-10`

Credible and Publisher are separate serving paths. Credible receives uploaded packages; Publisher needs either a local path or a copy inside its build context.

### 9.1 Local development without touching the deployed config

The Publisher supports a separate config file:

```text
--config <path>   default: <server_root>/publisher.config.json
```

Create a gitignored local workspace in `analytics-malloy-publisher-rag`:

```bash
cd /home/maxantipev/analytics-malloy-publisher-rag
mkdir -p workspace-local
```

`workspace-local/publisher.config.json`:

```json
{
  "frozenConfig": false,
  "environments": [
    {
      "name": "workspace",
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
        {
          "name": "comics",
          "location": "/home/maxantipev/analytics-engineering/semantic_layer/workspace/comics"
        },
        {
          "name": "jaffle_shop",
          "location": "/home/maxantipev/analytics-engineering/semantic_layer/workspace/jaffle_shop"
        }
      ]
    }
  ]
}
```

Use absolute paths in this local-only config. They avoid ambiguity about whether `location` is resolved from the config file or the process working directory.

Add the local workspace to `.gitignore`:

```gitignore
workspace-local/
```

Start Publisher:

```bash
cd /home/maxantipev/analytics-malloy-publisher-rag
set -a
source ../analytics-engineering/.env
set +a

npx --yes @malloy-publisher/server@0.0.244 \
  --server_root ./workspace-local \
  --config ./workspace-local/publisher.config.json \
  --port 4000 \
  --init \
  --watch-env workspace
```

`--watch-env` mounts the package directories in place, so edits in `analytics-engineering` are read live. This is a development convenience only. It is not a production packaging strategy.

Do not commit `workspace-local/` and do not point the deployed `workspace/publisher.config.json` at absolute laptop paths.

### 9.2 Add a deterministic copy step for deployment

The production image must contain real files. The existing Dockerfile does:

```dockerfile
COPY workspace/ ./workspace/
```

so anything placed in `workspace/semantic_layer/` before `docker build` is baked into the image.

Create `scripts/sync_semantic_layer.sh` in `analytics-malloy-publisher-rag`:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

SOURCE="${1:-../analytics-engineering/semantic_layer/workspace}"
DEST="${2:-workspace/semantic_layer}"

for package in comics jaffle_shop; do
  if [ ! -f "${SOURCE}/${package}/publisher.json" ]; then
    echo "[error] Missing package: ${SOURCE}/${package}/publisher.json" >&2
    exit 1
  fi
done

mkdir -p "$DEST"

rsync -a --delete \
  "${SOURCE}/" \
  "${DEST}/"

echo "[sync] Copied semantic packages to ${DEST}"
```

Make it executable:

```bash
chmod +x scripts/sync_semantic_layer.sh
```

The script fails before deleting anything if a package is missing. That prevents a partial checkout from wiping the deployed packages.

### 9.3 Keep the copied packages out of Git but inside the image

Add to `analytics-malloy-publisher-rag/.gitignore`:

```gitignore
workspace/semantic_layer/
```

Do **not** add `workspace/semantic_layer/` to `.dockerignore`. The build needs it.

Do **not** add `workspace/semantic_layer/` to `.gcloudignore` either. `gcloud builds submit` uses `.gcloudignore` when present, and an excluded directory never reaches Cloud Build even if it exists locally. The current `.gcloudignore` excludes Publisher state, caches, and `V3/`, but not `workspace/semantic_layer/`.

Current `.dockerignore` already excludes `.git/`, `node_modules/`, and Publisher databases. It does not exclude `workspace/semantic_layer/`, so no change is needed there.

### 9.4 Register the packages in the deployed config

Update `workspace/publisher.config.json`:

```json
{
  "frozenConfig": false,
  "environments": [
    {
      "name": "workspace",
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
        {
          "name": "thelook_ecommerce",
          "location": "./thelook_ecommerce"
        },
        {
          "name": "comics",
          "location": "./semantic_layer/comics"
        },
        {
          "name": "jaffle_shop",
          "location": "./semantic_layer/jaffle_shop"
        }
      ]
    }
  ]
}
```

The deployed config previously had an empty `connections` array because `thelook_ecommerce` uses local DuckDB/Parquet. The sample above adds `motherduck` because the semantic packages call `motherduck.table(...)`.

Inject `MOTHERDUCK_TOKEN` into Cloud Run. If the packages instead use embedded data or a DuckDB file inside the image, remove the `motherduck` connection and make the source prefix match the connection that actually exists.

The build-time RAG/context pipeline is a separate compiler path. It registers only `duckdb` and `bigquery`, so it cannot compile packages whose sources use `motherduck.table(...)`. Keep a second registry for that pipeline:

```json
{
  "frozenConfig": false,
  "environments": [
    {
      "name": "workspace",
      "connections": [],
      "packages": [
        {
          "name": "thelook_ecommerce",
          "location": "./thelook_ecommerce"
        }
      ]
    }
  ]
}
```

Save it as `workspace/publisher.context.config.json` and pass it to the pipeline in the Dockerfile:

```dockerfile
RUN python3 /app/context/orchestration/run_context_pipeline.py --all --fresh --index-chroma \
      --config /app/workspace/publisher.context.config.json
```

Publisher still reads `workspace/publisher.config.json`, so it serves all three packages. The context index remains limited to `thelook_ecommerce` until the compiler gains a MotherDuck connection. This is the §9.8 "MCP answers do not mention the new packages" limitation, not a Publisher load failure.

### 9.5 Build and verify locally

```bash
cd /home/maxantipev/analytics-malloy-publisher-rag

./scripts/sync_semantic_layer.sh

find workspace/semantic_layer -maxdepth 2 -name publisher.json -print
```

Expected:

```text
workspace/semantic_layer/comics/publisher.json
workspace/semantic_layer/jaffle_shop/publisher.json
```

Start the host Publisher against the gitignored `workspace-local` config and the real package folders:

```bash
set -a
source ../analytics-engineering/.env
set +a

npx --yes @malloy-publisher/server@0.0.244 \
  --server_root ./workspace-local \
  --config ./workspace-local/publisher.config.json \
  --port 4000 \
  --init \
  --watch-env workspace
```

Observed on 2026-10-20:

```text
GET /api/v0/status -> operationalState: serving, loadErrors: null
packages: thelook_ecommerce, comics, jaffle_shop
comics: 3,312 rows
jaffle_shop: 686 orders, 7,226.67 revenue
```

If the Docker daemon is not available in the current environment, do not treat that as a blocker. `gcloud builds submit` runs the same Dockerfile remotely and is the production build path. The first attempt of this task failed inside that image because the context pipeline tried to compile the MotherDuck packages with the DuckDB/BigQuery-only compiler; §9.4's separate `publisher.context.config.json` fixes the build without weakening Publisher's config.

After a successful build:

```bash
gcloud run deploy malloy-publisher-mcp \
  --image gcr.io/my-1-st-project-training/malloy-publisher-mcp:latest \
  --platform managed \
  --region northamerica-northeast1 \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 3 \
  --memory 4Gi \
  --cpu 2 \
  --cpu-boost \
  --timeout 600 \
  --port 5050 \
  --set-secrets=MOTHERDUCK_TOKEN=motherduck-token:latest
```

Use the deployed `/mcp` endpoint to spot-check both packages, because Cloud Run exposes port `5050` (the Node MCP/API), not the internal UI port `4000`:

```bash
curl -fsS "https://malloy-publisher-mcp-bolcwt6srq-nn.a.run.app/api/v0/status"
```

Observed after revision `malloy-publisher-mcp-00028-ric`:

```text
operationalState: serving
loadErrors: null
packages: thelook_ecommerce, comics, jaffle_shop
comics_explore -> Comic_Count: 3312
cafe_explore -> Order_Count: 686, Total_Revenue: 7226.67
```

`docker build` and `docker run` are still the right local checks on a machine with a working Docker daemon; the `find` and query expectations above are the same.

### 9.6 Optional automation: notify the Publisher repository

> **Status:** superseded design. `TASK-09a` in §9A replaces this `repository_dispatch` sketch with a same-repository `workflow_run` workflow that needs no cross-repository token. Keep this section as the historical alternative; do not implement both.

The Publisher repository is separate, so a push to `analytics-engineering` does not build it. Use a `repository_dispatch` event.

Create `.github/workflows/notify-publisher.yml` in `analytics-engineering`:

```yaml
name: Notify Publisher

on:
  push:
    branches: [main]
    paths:
      - 'semantic_layer/workspace/**'
  workflow_dispatch:

permissions:
  contents: read

jobs:
  dispatch:
    runs-on: ubuntu-latest

    steps:
      - name: Send repository dispatch
        env:
          GH_TOKEN: ${{ secrets.PUBLISHER_DISPATCH_TOKEN }}
        run: |
          gh api \
            repos/antipev/analytics-malloy-publisher-rag/dispatches \
            -f event_type=semantic-layer-updated
```

`PUBLISHER_DISPATCH_TOKEN` must be a fine-grained token with access to `antipev/analytics-malloy-publisher-rag` and **Contents: Read and write** (the permission GitHub requires for `repository_dispatch`). Store it as a secret in `analytics-engineering`.

In `analytics-malloy-publisher-rag`, add `ANALYTICS_REPO_TOKEN` as a repository secret: a fine-grained token with **Contents: Read** on `antipev/analytics-engineering`. Then add a workflow that reacts to the event:

```yaml
name: Deploy semantic layer

on:
  repository_dispatch:
    types: [semantic-layer-updated]
  workflow_dispatch:

permissions:
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - name: Check out Publisher
        uses: actions/checkout@v4
        with:
          path: publisher
          fetch-depth: 0

      - name: Check out analytics-engineering
        uses: actions/checkout@v4
        with:
          repository: antipev/analytics-engineering
          token: ${{ secrets.ANALYTICS_REPO_TOKEN }}
          path: analytics
          fetch-depth: 1

      - name: Copy semantic packages
        working-directory: publisher
        run: |
          ./scripts/sync_semantic_layer.sh \
            ../analytics/semantic_layer/workspace

      - name: Build and deploy
        working-directory: publisher
        run: |
          # Use the project's existing GCP authentication and deployment
          # commands from DEPLOYMENT.md §6. The required order is:
          #
          #   gcloud builds submit \
          #     --tag gcr.io/my-1-st-project-training/malloy-publisher-mcp .
          #
          #   gcloud run deploy malloy-publisher-mcp \
          #     --image gcr.io/my-1-st-project-training/malloy-publisher-mcp \
          #     --platform managed \
          #     --region northamerica-northeast1 \
          #     --allow-unauthenticated \
          #     --min-instances 0 \
          #     --max-instances 3 \
          #     --memory 4Gi \
          #     --cpu 2 \
          #     --cpu-boost \
          #     --timeout 600 \
          #     --port 5050 \
          #     --set-secrets=MOTHERDUCK_TOKEN=motherduck-token:latest
          echo "Configure GCP authentication before using these commands." >&2
          exit 1
```

The final `exit 1` is deliberate: the workflow fails until the repository's actual authentication step (`google-github-actions/auth`, Workload Identity Federation, or a service-account secret) is added and the commented deployment commands are enabled. The deployment command itself comes from `DEPLOYMENT.md` §6.

A Cloud Build trigger alone is not sufficient if it builds only the Publisher repository: the build context would not contain `semantic_layer/workspace`. The checkout of both repositories, the `rsync`, and the image build must happen in the same job or build context.

### 9.7 Verify the deployed Publisher

After deployment:

```bash
PUBLISHER_URL="https://malloy-publisher-mcp-bolcwt6srq-nn.a.run.app"

curl -fsS "${PUBLISHER_URL}/api/v0/status" | jq
```

Confirm:

- [ ] `operationalState` is `serving`.
- [ ] `loadErrors` is empty.
- [ ] `comics` and `jaffle_shop` are listed alongside `thelook_ecommerce`.
- [ ] A query against `cafe_orders` returns rows.
- [ ] A query against `comics` returns rows.

Check the logs if a package is missing:

```bash
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=malloy-publisher-mcp" \
  --limit 50 \
  --format="table(timestamp, textPayload)"
```

### 9.8 Publisher failure modes

**Package is missing from the UI**

- `workspace/semantic_layer/<package>` was not present at `docker build` time.
- The `COPY workspace/ ./workspace/` layer ran before the sync.
- The package is not listed in `workspace/publisher.config.json`.

**`loadErrors` mentions `motherduck`**

- The deployed config has no `motherduck` connection.
- `MOTHERDUCK_TOKEN` is not injected into Cloud Run.
- The token is invalid or lacks access to `data_warehouse_demo`.

**Package loads locally but not in Cloud Run**

- Local `--watch-env` was used with absolute paths. Those paths do not exist in the image.
- The deployed image used `workspace/semantic_layer/` but the config still points at `../../analytics-engineering/...`.

**MCP answers do not mention the new packages**

This is expected for the current build. The Python RAG/context pipeline uses `workspace/publisher.context.config.json`, which contains only `thelook_ecommerce` because the build-time compiler has no MotherDuck connection. Publisher's own config still serves `comics` and `jaffle_shop`. To add MCP coverage, extend the compiler with a MotherDuck connection and add the packages to the context config, then rebuild the index; do not remove them from `workspace/publisher.config.json`.

### 9.9 Phase 8 verification checklist

> The two `Optional automation only` items are intentionally unchecked. §9.6 is superseded by the executed `TASK-09a` design in §9A; `TASK-09` deliberately used the manual sync + build + deploy path.

- [x] Local `workspace-local/` config uses absolute paths and is gitignored.
- [x] Local Publisher serves both packages with `--watch-env`.
- [x] `scripts/sync_semantic_layer.sh` is executable and fails on missing packages.
- [x] `workspace/semantic_layer/` is gitignored.
- [x] `workspace/semantic_layer/` is **not** in `.dockerignore`.
- [x] `workspace/semantic_layer/` is **not** in `.gcloudignore`.
- [x] `workspace/publisher.config.json` lists both packages at `./semantic_layer/...`.
- [x] The Docker image build succeeds and contains `workspace/semantic_layer/*/publisher.json` (verified by Cloud Build pipeline output; local `docker build` unavailable here).
- [x] The deployed service reports `operationalState: serving`.
- [x] `loadErrors` is empty.
- [x] Both packages are queryable through the deployed Publisher/MCP endpoint.
- [ ] Optional automation only: `PUBLISHER_DISPATCH_TOKEN` exists in `analytics-engineering`.
- [ ] Optional automation only: `ANALYTICS_REPO_TOKEN` exists in `analytics-malloy-publisher-rag`.
- [x] No absolute laptop path is committed.
- [x] No token is baked into the image or committed.

## 9A. Phase 8 follow-up — Automate Publisher deployment (`TASK-09a`)

> **Tag:** `TASK-09a` | **Type:** execution | **Status:** `DONE` — manual and automatic paths proven 2026-10-21 | **Exit gate:** §9A.7 | **Next:** none; the deprecated `publisher.json.explores` migration remains a separate deferred task.

This is a design and execution record. `TASK-09` proved the manual path. `TASK-09a` removes the manual `rsync` → `gcloud builds submit` → `gcloud run deploy` sequence while keeping `analytics-engineering` as the only canonical source. On 2026-10-21 the build-time copy, WIF setup, workflow, Cloud Build, Cloud Run deployment, automatic `workflow_run` trigger, MCP queries, rollback rehearsal, and failed-publish safety check were all executed.

### 9A.0 The solution in plain English

**The problem.** The Malloy models that Publisher must serve live in `analytics-engineering/semantic_layer/workspace/`. The Publisher application, its `Dockerfile`, and its runtime configuration live in the separate `analytics-malloy-publisher-rag` repository. Credible publishing only uploads the packages to Credible; it does not rebuild Publisher. Therefore, after a model change is merged and published, the deployed Publisher keeps serving the previous image until someone manually runs `sync_semantic_layer.sh`, Cloud Build, and Cloud Run deploy.

**The solution.** Add one workflow to `analytics-engineering`: `.github/workflows/deploy-publisher.yml`. After the existing `Bump and Publish Packages` workflow succeeds, that workflow:

1. Checks out the latest `analytics-engineering` `main`, including the bot's version-bump commit.
2. Checks out the Publisher repository into a `publisher/` subdirectory.
3. Copies `semantic_layer/workspace/comics` and `semantic_layer/workspace/jaffle_shop` into `publisher/workspace/semantic_layer/` **inside the CI build directory only**.
4. Builds a new Docker image from `publisher/` and deploys that exact image to Cloud Run.
5. Waits until Publisher reports `serving` and lists both packages; a failed check fails the workflow.

The semantic packages are **not fetched from Credible**, and they are **not committed into the Publisher repository**. Credible and Publisher are two consumers of the same Git source. The workflow copies the files from `analytics-engineering` into the Publisher build context at build time, so the resulting image contains its own copy of the models.

In this document, **"published"** means uploaded to Credible, while **"deployed"** means a new Publisher image is running on Cloud Run. "Newly pushed models" means the `.malloy` changes that were merged to `main`; Publisher never reads Credible's package store.

**The concrete source-to-serving path (important):**

```text
analytics-engineering/semantic_layer/workspace/
    comics/
    jaffle_shop/
                │
                │ copied into the CI build directory
                ▼
analytics-malloy-publisher-rag/workspace/semantic_layer/
    comics/
    jaffle_shop/
                │
                │ Cloud Build uses the Publisher repo Dockerfile
                ▼
        Container image
                │   contains /app/workspace/semantic_layer/{comics,jaffle_shop}
                ▼
           Cloud Run
```

The copy is **not** committed or pushed to GitHub. The second path exists only in the CI runner's checked-out copy of the Publisher repository. It is then baked into the image by `COPY workspace/ ./workspace/`. The Publisher repository on GitHub keeps only its tracked files: application code, `Dockerfile`, `workspace/publisher.config.json`, `thelook_ecommerce`, and the context scripts.

Publisher's `workspace/publisher.config.json` points at `./semantic_layer/comics` and `./semantic_layer/jaffle_shop`, relative to the server root `workspace`. That is why the copy must land in `publisher/workspace/semantic_layer/`, not somewhere else.

The destination directory is named **`semantic_layer`**, matching the source directory name. The sync script, `publisher.config.json`, `.gitignore`, the workflow, and the deployment documentation all use the same name. The directory remains generated and gitignored; only the name changed.

### 9A.0.1 Options for connecting the two repositories

| Option | What it would mean | Does it work? | Verdict |
| :--- | :--- | :--- | :--- |
| **A** | Add an empty `workspace/semantic_layer/` folder to the Publisher repository and treat it as “linked” to `analytics-engineering/semantic_layer/` | No. Git does not track empty directories, and a folder cannot point at another repository | Reject |
| **B** | Add a Git symlink in the Publisher repository to `analytics-engineering/semantic_layer/` | No. A Git symlink stores a path, not the files. Cloud Build receives only the Publisher repository, so the target is missing | Reject |
| **C** | In CI, check out both repositories, copy `analytics-engineering/semantic_layer/workspace/*` into the Publisher build directory, then build the image | Yes. The image is self-contained and Cloud Build needs only the Publisher repository as its source | **Select** |

**Option A — empty `workspace/semantic_layer/` folder.** Git does not version empty directories, so this folder would not reliably exist after checkout. A `.gitkeep` file could make it visible, but it would still contain no models. Nothing would connect it to the analytics repository; Publisher would try to load an empty package and report load errors. If “linked” means a Git submodule, that is a different design: it pins a second repository, requires recursive checkout and credentials, and creates the same duplicated-source problem as committing the files. Reject.

**Option B — cross-repository symlink.** A Git symlink is committed as a path string, not as the target's contents. On GitHub it is only a link. In Cloud Build, the source archive contains the Publisher repository, not its sibling `analytics-engineering` checkout, so a relative symlink is dangling and an absolute symlink points at a path that does not exist in the build. It can appear to work only on one developer's laptop, which is the opposite of reliable. Reject.

**Option C — build-time copy (recommended).** The workflow checks out both repositories in the same CI job, runs `scripts/sync_semantic_layer.sh` to copy `semantic_layer/workspace/*` into `publisher/workspace/semantic_layer/`, and then runs Cloud Build from `publisher/`. The copy is not committed. The image contains exactly what was built, and the immutable image tag identifies it. This has the smallest code surface: the sync script already exists, and `TASK-09a` adds one workflow. It is also the easiest to explain: the CI log shows the copy, the Docker build shows the image contents, and the Cloud Run revision points at that image.

**Decision: option C.** Do not add a placeholder folder or symlink to the Publisher repository. Do not commit the generated copy. Copy it in the CI runner, bake it into the image, and let the image tag be the record of what was deployed.

Option C is a **build-time copy**, not a commit. The variant that commits the generated files back to the Publisher repository is separately rejected in §9A.2.

**What happens after a developer changes a model:**

| Step | What runs | Result |
| :--- | :--- | :--- |
| 1 | Developer edits `semantic_layer/workspace/comics/**.malloy` and merges to `main` | Normal pull request and review |
| 2 | `deploy.yaml` detects the changed package, bumps its version, commits `chore: auto-bump ... [skip ci]`, and publishes to Credible | Credible gets the new package version |
| 3 | `deploy-publisher.yml` starts because the publish workflow succeeded | A separate deployment run, not a second publish |
| 4 | Workflow checks out latest `main` and the Publisher repo | Both the new model and the Publisher application are present in the runner |
| 5 | `sync_semantic_layer.sh` validates and copies both packages | `publisher/workspace/semantic_layer/` exists only in the runner |
| 6 | Cloud Build builds an immutable `sha-<commit>` image | The image contains the new models |
| 7 | Cloud Run deploys that image with the existing MotherDuck secret | New revision receives traffic after a successful deploy |
| 8 | Smoke test checks `serving` plus `comics` and `jaffle_shop` | A broken image fails the workflow instead of silently serving old or partial content |

A normal package change therefore needs no manual Publisher command. The engineer merges the model change; the two workflows publish to Credible and deploy Publisher from the same commit.

**What is new versus what already exists:**

| Component | Status after `TASK-09` | `TASK-09a` action |
| :--- | :--- | :--- |
| Canonical models in `analytics-engineering/semantic_layer/workspace/` | Exist | No change |
| Publisher `Dockerfile`, `workspace/publisher.config.json`, ignore files | Updated and committed in `analytics-malloy-publisher-rag` (`228eac02`, then `777c6eef` for the `semantic_layer` name) | No change per release |
| `scripts/sync_semantic_layer.sh` | Exists and is executable | Called by CI; default destination is `workspace/semantic_layer` |
| `.github/workflows/deploy-publisher.yml` | Did not exist | **Created and pushed** in `b651feb` |
| GCP Workload Identity Federation and two repository secrets | Did not exist | **Created 2026-10-21**, §9A.5 |
| Cloud Build and Cloud Run deployment | Manual | Automated by the new workflow; manual dispatch and automatic `workflow_run` both proven |

**How the implementation was done, in order:**

1. [x] Resolve the design decisions in §9A.8 using the defaults recorded there.
2. [x] Run the one-time GCP setup in §9A.5 and create `GCP_WORKLOAD_IDENTITY_PROVIDER` and `GCP_SERVICE_ACCOUNT` in the `analytics-engineering` repository.
3. [x] Add `.github/workflows/deploy-publisher.yml` as shown in §9A.4 and push it to `main` (`b651feb`).
4. [x] Run it with `workflow_dispatch` to prove checkout, sync, build, deploy, and smoke test without changing a model (run `39621809476`).
5. [x] Make one small real model change, merge it, and verify that Credible publish and Publisher deploy both complete and that the new behavior is visible through Publisher and MCP (`f4a5b6b`; publish run `39696122370`; deploy run `39696218691`).
6. [x] Rehearse rollback by sending traffic back to the previous Cloud Run revision (`00028-2nc`), then restore the current revision (`00029-fzp`).
7. [x] Prove that a failed Credible publish does not deploy (`c955271` → publish run `39697920035` failed; deploy run `39698014901` skipped; revision stayed `00029-fzp`), then revert and recover (`81deb7c`).
8. [x] Record the results in §9A.0.2 and mark `TASK-09a` `DONE`.

**Guardrails:**

- If either package is missing, the sync script exits before deleting anything, so a partial checkout cannot produce an image with one package silently removed.
- If Cloud Build fails, no deploy command runs.
- If the Cloud Run deploy fails, traffic stays on the previous healthy revision.
- If the smoke test fails, the workflow is red and the operator rolls traffic back to the previous revision; the image tag identifies exactly what was attempted.
- `workspace/semantic_layer/` is gitignored, but it is not listed in `.dockerignore` or `.gcloudignore`; it exists only in the build context and the image.
- The workflow never receives a Credible token, a MotherDuck token, or a Publisher-repository write token. Cloud Run injects the MotherDuck secret at deploy time.

### 9A.0.2 Execution record (2026-10-21 to 2026-10-22)

| Item | Result |
| :--- | :--- |
| Publisher repository rename | Commit `777c6eef`: `sync_semantic_layer.sh`, `workspace/publisher.config.json`, `.gitignore`, and `DEPLOYMENT.md` now use `workspace/semantic_layer/` |
| Workflow | Commit `b651feb`: `.github/workflows/deploy-publisher.yml`, targeting `workspace/semantic_layer`; hardened in `fb46b1c` to assert the new revision receives traffic before the smoke test |
| WIF pool/provider | `github-pool` / `github-provider` in project `669258319971`; condition restricts to `antipev/analytics-engineering` at `refs/heads/main` |
| Repository secrets | `GCP_WORKLOAD_IDENTITY_PROVIDER` and `GCP_SERVICE_ACCOUNT` in `antipev/analytics-engineering` |
| Manual workflow run | [Run `39621809476`](https://github.com/antipev/analytics-engineering/actions/runs/39621809476) — success |
| Manual build and release | Cloud Build `ed39e5d9-0407-49a4-8a81-4b316a1738d9` — `SUCCESS`; image `sha-b651feb0dda9`; revision `malloy-publisher-mcp-00028-2nc`, 100% traffic |
| Automatic trigger | Model commit `f4a5b6b`; [publish run `39696122370`](https://github.com/antipev/analytics-engineering/actions/runs/39696122370) — success; bot bump `a6e1383`; [deploy run `39696218691`](https://github.com/antipev/analytics-engineering/actions/runs/39696218691) — success |
| Published versions | `comics@0.1.2` and `jaffle_shop@0.1.2`; both package URLs returned by `cred` |
| Automatic build and release | Cloud Build `fb741174-d469-440b-aa52-3db18fd6a7ef` — `SUCCESS`; image `sha-a6e13834b61d`; revision `malloy-publisher-mcp-00029-fzp`, 100% traffic |
| Version parity | The deploy checked out `a6e1383`; both `publisher.json` files contain `0.1.2`, matching the two Credible versions published immediately before the deploy |
| No second run | The run list contains exactly one `Bump and Publish Packages` and one `Deploy Publisher` for `f4a5b6b`; the `a6e1383` `[skip ci]` bump started neither |
| MCP query correctness | `comics_explore` returned `Comic_Count: 3312`; `cafe_explore` returned `Order_Count: 686` and `Total_Revenue: 7226.67` |
| Live status | `operationalState: serving`; environment `workspace`; packages `thelook_ecommerce`, `comics`, `jaffle_shop`; startup log `load_errors=0` |
| Rollback rehearsal | Traffic moved to `malloy-publisher-mcp-00028-2nc=100`, verified healthy, then restored to `malloy-publisher-mcp-00029-fzp=100` |
| Failed-publish safety | `c955271` introduced an invalid `cafe_explore` model; the bump succeeded (`jaffle_shop@0.1.3`) but [publish run `39697920035`](https://github.com/antipev/analytics-engineering/actions/runs/39697920035) failed compilation after 3 attempts; [deploy run `39698014901`](https://github.com/antipev/analytics-engineering/actions/runs/39698014901) was `skipped`; traffic stayed on `00029-fzp` |
| Recovery | Revert `81deb7c`; [publish run `39698140249`](https://github.com/antipev/analytics-engineering/actions/runs/39698140249) published `jaffle_shop@0.1.4`; [deploy run `39698234168`](https://github.com/antipev/analytics-engineering/actions/runs/39698234168) built `sha-aa7e126f3099` and created revision `00030-z9m` |
| Recovery routing defect | Cloud Run created `00030-z9m`, but traffic remained on `00029-fzp`; the smoke test therefore passed against the old revision. Manual `update-traffic --to-latest` moved `00030-z9m` to 100%, and workflow commit `fb46b1c` added an explicit routing step that asserts the latest revision is active before the smoke test |
| Hardened workflow validation | Manual [run `39699737003`](https://github.com/antipev/analytics-engineering/actions/runs/39699737003) — success; Cloud Build `5c13135a-2d1e-4290-b4e5-2ca99c4d30d4`; image `sha-fb46b1cface7`; revision `malloy-publisher-mcp-00031-2sd`, 100% traffic; routing and smoke-test steps both passed |
| Current production | `malloy-publisher-mcp-00031-2sd` at 100%; image `sha-fb46b1cface7`; `comics@0.1.2`, `jaffle_shop@0.1.4`; status `serving`; `Comic_Count: 3312` re-verified on this revision |
| Current rollback target | `malloy-publisher-mcp-00030-z9m`; older retained revisions `00028-2nc` and `00028-ric` (image digest `sha256:8ba5a3eb0adb5b233812acefcbc8ce7f4056c2847afb0e173db06b315e9b7aef`) |

The first WIF attempt authenticated successfully but `gcloud builds submit` failed with `iam.serviceAccounts.getAccessToken` denied. The WIF principal had `roles/iam.workloadIdentityUser` but still could not refresh the impersonated credential. Adding `roles/iam.serviceAccountTokenCreator` on `malloy-analytics-user` for the same principalSet fixed it. Both bindings are required in this setup; record them in §9A.5.

The generated `workspace/semantic_layer/` directory intentionally does **not** appear in the Publisher repository on GitHub. The workflow creates it in the CI checkout (`publisher/workspace/semantic_layer/`), Cloud Build bakes it into the image, and the image tag/revision is the deployment record. See §9A.0.1 for the rejected alternatives.

The manual and automatic paths, query correctness, rollback, and failed-publish safety are now proven. The recovery deploy also exposed a stale-traffic risk in the original smoke test; `fb46b1c` closes it and was validated by a fresh manual deploy.

### 9A.1 Goal and non-goals

**Goal:** after a push to `main` changes `semantic_layer/workspace/**`, and after the Credible bump/publish workflow succeeds, rebuild the Publisher image from the current canonical packages and deploy it to Cloud Run. The deployed Publisher must serve the same package versions that Credible just published.

**Non-goals:**

- Do not migrate `publisher.json` from `explores` to `index.malloy`; see §9A.3.
- Do not add a second copy of the semantic packages as committed source.
- Do not make Publisher deploy on the bot's `[skip ci]` version-bump commit.
- Do not change the Publisher's `thelook_ecommerce` package, its context/RAG configuration, or its MotherDuck secret.
- Do not expose a service-account key, `MOTHERDUCK_TOKEN`, or any other secret to the workflow.

### 9A.2 Alternatives considered

#### Selected: same-repository workflow triggered by `workflow_run`

Add `.github/workflows/deploy-publisher.yml` to `analytics-engineering`. It runs after the existing `Bump and Publish Packages` workflow completes successfully, checks out the latest `main` (including the bot's version-bump commit), checks out the public Publisher repository as a build context, runs the existing sync script, and builds/deploys.

Why this is the recommended design:

- The canonical source and the automation live in the same repository, so a package change and its deployment behavior are reviewed together.
- No cross-repository write token is required. The Publisher repository is checked out read-only; the only credential is the GCP workload identity.
- The generated `workspace/semantic_layer/` copy exists only in the CI workspace and in the image. It is never committed.
- `workflow_run` runs after `publish`, so the checked-out `publisher.json` versions match the Credible versions that were just published.
- The bot commit contains `[skip ci]`; it does not start a second publish or deploy loop.

#### Rejected: CI commits generated files into the Publisher repository

One alternative is for `analytics-engineering` CI to run the sync script and commit `workspace/semantic_layer/` into `analytics-malloy-publisher-rag`, which would then build on its own push. This is not recommended:

1. **It creates a second source of truth.** The same Malloy files would exist in both repositories, and a human could edit the generated copy. The next sync would silently overwrite that edit.
2. **It adds commit noise and races.** Every package change becomes a generated commit in another repository; concurrent package changes need rebases or force-pushes, and a failed sync can leave the Publisher repository at a half-updated state.
3. **It requires a write credential to the Publisher repository.** A GitHub App or fine-grained PAT with contents write is a larger blast radius than a read-only checkout, and it must be rotated.
4. **It does not remove the build step.** The Publisher repository still needs a workflow to build and deploy after the generated commit, so the design has all of the coupling and none of the simplicity.
5. **It makes rollback ambiguous.** Reverting a generated commit does not reliably restore the image that was serving; the image tag and revision are the real rollback unit.

The same-repository workflow keeps one source, one commit history, and one review surface.

#### Alternative: add a `publisher` job to `deploy.yaml`

A `publisher` job after `publish` with `needs: [bump, publish]` and `if: needs.bump.outputs.bumped != ''` is the smallest possible change. It avoids `workflow_run` and is guaranteed to run only when the bump job found packages. The trade-off is that the Credible publish workflow and the Publisher deployment share one workflow file, one concurrency group, and one failure surface. It is a reasonable fallback if `workflow_run` proves awkward; the same build/deploy steps below apply.

#### Rejected: Cloud Build trigger on the Publisher repository alone

A Cloud Build trigger that watches only `analytics-malloy-publisher-rag` cannot see `semantic_layer/workspace`. It would build an image without the packages. The checkout of both repositories and the `rsync` must happen in the same build context; see §9.6.

### 9A.3 Manifest decision: keep `explores` for now

Publisher currently logs:

```text
"explores" in publisher.json is deprecated
```

The warning is real, but the current behavior is correct:

- `comics/publisher.json` declares `3_explores/comics_explore.malloy`.
- `jaffle_shop/publisher.json` declares `3_explores/cafe_explore.malloy`.
- Publisher exposes exactly `comics_explore` and `cafe_explore`; no refinement or private source leaks.
- Both sources return rows through Publisher and Credible.

The replacement is an `index.malloy` at each package root. That is a **surface migration**, not a cosmetic file rename: it changes what the package declares as queryable and must be validated in Credible, the Publisher UI, the deployed MCP endpoint, and the RAG/context pipeline. It is deliberately deferred.

**Decision:** keep `explores` and accept the warning until a separate migration is approved. If a future Publisher release removes support, treat that release as a breaking change and schedule the `index.malloy` migration before upgrading. Record the migration as a follow-up, not as a hidden part of this automation task.

### 9A.4 Proposed workflow

Add `.github/workflows/deploy-publisher.yml`:

```yaml
name: Deploy Publisher

on:
  workflow_run:
    workflows: ["Bump and Publish Packages"]
    types: [completed]
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  id-token: write

concurrency:
  group: publisher-deploy-${{ github.ref }}
  cancel-in-progress: false

jobs:
  deploy:
    if: |
      github.event_name == 'workflow_dispatch' ||
      (github.event.workflow_run.conclusion == 'success' &&
       github.event.workflow_run.event == 'push')
    runs-on: ubuntu-latest

    env:
      PROJECT_ID: my-1-st-project-training
      REGION: northamerica-northeast1
      SERVICE: malloy-publisher-mcp
      IMAGE_NAME: gcr.io/my-1-st-project-training/malloy-publisher-mcp

    steps:
      - name: Check out canonical packages at the latest main
        uses: actions/checkout@v4
        with:
          ref: main
          fetch-depth: 0

      - name: Check out Publisher build context
        uses: actions/checkout@v4
        with:
          repository: antipev/analytics-malloy-publisher-rag
          path: publisher
          fetch-depth: 1

      - name: Authenticate to Google Cloud with workload identity
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.GCP_WORKLOAD_IDENTITY_PROVIDER }}
          service_account: ${{ secrets.GCP_SERVICE_ACCOUNT }}

      - name: Set up gcloud
        uses: google-github-actions/setup-gcloud@v2

      - name: Resolve immutable image tag
        id: image
        run: echo "tag=sha-$(git rev-parse --short=12 HEAD)" >> "$GITHUB_OUTPUT"

      - name: Copy the semantic packages into the build context
        working-directory: publisher
        run: |
          chmod +x ./scripts/sync_semantic_layer.sh
          ./scripts/sync_semantic_layer.sh \
            ../semantic_layer/workspace \
            workspace/semantic_layer

      - name: Build the Publisher image
        working-directory: publisher
        env:
          IMAGE: ${{ env.IMAGE_NAME }}:${{ steps.image.outputs.tag }}
        run: |
          gcloud builds submit \
            --project "$PROJECT_ID" \
            --tag "$IMAGE" \
            --quiet \
            .

      - name: Deploy the Cloud Run revision
        env:
          IMAGE: ${{ env.IMAGE_NAME }}:${{ steps.image.outputs.tag }}
        run: |
          gcloud run deploy "$SERVICE" \
            --project "$PROJECT_ID" \
            --image "$IMAGE" \
            --platform managed \
            --region "$REGION" \
            --allow-unauthenticated \
            --min-instances 0 \
            --max-instances 3 \
            --memory 4Gi \
            --cpu 2 \
            --cpu-boost \
            --timeout 600 \
            --port 5050 \
            --set-secrets=MOTHERDUCK_TOKEN=motherduck-token:latest \
            --quiet

      - name: Smoke-test the deployed service
        run: |
          URL=$(gcloud run services describe "$SERVICE" \
            --project "$PROJECT_ID" \
            --region "$REGION" \
            --format='value(status.url)')

          for attempt in $(seq 1 24); do
            status=$(curl -fsS "${URL}/api/v0/status" || true)
            if printf '%s' "$status" | grep -q '"operationalState":"serving"' &&
               printf '%s' "$status" | grep -q '"comics"' &&
               printf '%s' "$status" | grep -q '"jaffle_shop"'; then
              echo "Publisher is serving both semantic packages."
              exit 0
            fi
            echo "Waiting for Publisher (${attempt}/24)..."
            sleep 10
          done

          echo "Publisher did not reach a serving state with both packages." >&2
          exit 1
```

Notes:

- `sync_semantic_layer.sh` already fails before deleting anything if a package is missing. That behavior is required here: a partial checkout must fail the deploy rather than ship an image without a package.
- `workspace/semantic_layer/` must remain outside `.dockerignore` and `.gcloudignore`; otherwise the copy exists in CI but never reaches the image.
- The image tag is derived from the checked-out commit after the bot bump. Do not deploy the mutable `:latest` tag from CI; an immutable tag makes the Cloud Run revision and rollback unambiguous.
- The smoke test checks package names in the status payload, not `loadErrors`, because the current status response does not expose a top-level `loadErrors` field. The startup log's `load_errors=0` is the build-time check; the deployed query is the runtime check.
- If the Publisher repository ever becomes private, add a read-only deploy key or fine-grained token for the second checkout. Do not give the workflow write access.

### 9A.5 GCP setup — reusing `malloy-analytics-user`

The confirmed service account is:

```text
malloy-analytics-user@my-1-st-project-training.iam.gserviceaccount.com
```

Use Workload Identity Federation; do not create a JSON service-account key. The setup commands below were executed on 2026-10-21 and are kept as the reproducible record:

```bash
PROJECT_ID="my-1-st-project-training"
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
SA="malloy-analytics-user@${PROJECT_ID}.iam.gserviceaccount.com"

# 1. Confirm the service account exists.
gcloud iam service-accounts describe "$SA" --project "$PROJECT_ID"

# 2. Grant the deploy/build roles. Review existing bindings first; do not
#    duplicate a broader role that is already present.
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA}" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA}" \
  --role="roles/cloudbuild.builds.editor"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA}" \
  --role="roles/iam.serviceAccountUser"

# 3. Cloud Build uploads the source archive and pushes the image to GCR.
#    Scope this to the project's Cloud Build staging bucket and GCR bucket
#    if the team does not want project-level storage admin.
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA}" \
  --role="roles/storage.admin"

# 4. Create the workload identity pool and provider once.
gcloud iam workload-identity-pools create github-pool \
  --project "$PROJECT_ID" \
  --location global \
  --display-name "GitHub Actions"

gcloud iam workload-identity-pools providers create-oidc github-provider \
  --project "$PROJECT_ID" \
  --location global \
  --workload-identity-pool github-pool \
  --display-name "Analytics Engineering main" \
  --issuer-uri "https://token.actions.githubusercontent.com" \
  --attribute-mapping "google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
  --attribute-condition "assertion.repository == 'antipev/analytics-engineering' && assertion.ref == 'refs/heads/main'"

# 5. Allow only this repository's main branch to impersonate the service account.
gcloud iam service-accounts add-iam-policy-binding "$SA" \
  --project "$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/attribute.repository/antipev/analytics-engineering"

# 6. Required in practice for gcloud's impersonated-credential refresh.
#    Without this binding, the auth step succeeds but `gcloud builds submit`
#    fails with iam.serviceAccounts.getAccessToken denied.
gcloud iam service-accounts add-iam-policy-binding "$SA" \
  --project "$PROJECT_ID" \
  --role="roles/iam.serviceAccountTokenCreator" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/attribute.repository/antipev/analytics-engineering"
```

> **Executed state:** `malloy-analytics-user` already holds `roles/owner` on the project, so the four project-level role bindings in step 2/3 were not added; `roles/storage.admin` was not needed. The pool, provider, `roles/iam.workloadIdentityUser`, and `roles/iam.serviceAccountTokenCreator` bindings were created. A future least-privilege cleanup should replace `roles/owner` with the listed roles, but that is separate from the proven deployment path.

Then add two repository secrets in `analytics-engineering`:

| Secret | Value |
| :--- | :--- |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | `projects/<PROJECT_NUMBER>/locations/global/workloadIdentityPools/github-pool/providers/github-provider` |
| `GCP_SERVICE_ACCOUNT` | `malloy-analytics-user@my-1-st-project-training.iam.gserviceaccount.com` |

Do **not** add a `GCP_SA_KEY` or any JSON key. The WIF provider condition restricts the token to `main` in this repository.

Least-privilege refinement: if `roles/storage.admin` is too broad, replace it with object-admin on the Cloud Build staging bucket plus the GCR bucket; `roles/cloudbuild.builds.editor` and `roles/run.admin` remain. A dedicated `github-publisher-deployer` service account would be cleaner than reusing `malloy-analytics-user`; the user selected the existing account, so the task should verify its current roles and add only what is missing.

### 9A.6 Version alignment, triggers, and failure behavior

**Version alignment:** the existing `publish` job checks out the latest `main` after the bot commit. `workflow_run` then starts only after that job succeeds, and the Publisher workflow checks out `main` again. The copied `publisher.json` files therefore contain the versions that Credible published. The Publisher workflow does not need to wait for `buildStatus: READY`; publishing and image building are independent, but the versions and source content match.

**Loop prevention:** the bump job does not run on the bot's `chore: auto-bump ... [skip ci]` commit. The Publisher workflow is triggered by the `Bump and Publish Packages` run, not by the bot commit, so it runs once per source push.

**Failure behavior:**

| Failure | Result |
| :--- | :--- |
| Credible bump/publish fails | `workflow_run` sees `conclusion: failure` and does not deploy. Cloud Run keeps the previous revision. |
| Package compile fails during sync or build | `sync_semantic_layer.sh` or Cloud Build fails; no new revision. |
| Cloud Build succeeds, deploy fails | The image exists but Cloud Run keeps the previous ready revision; rerun the workflow after fixing IAM. |
| Deploy succeeds, smoke test fails | The new revision may be live; inspect `gcloud run revisions list` and roll traffic back to the previous revision. |
| Push contains no package change | The original workflow's path filter prevents this case. If a path matched but no `publisher.json` was found, the bump job is a no-op and the Publisher job may redeploy an unchanged image; acceptable, but the `publisher` job in `deploy.yaml` is the tighter alternative. |

### 9A.7 Verification checklist

- [x] `.github/workflows/deploy-publisher.yml` is on `main`; GitHub parsed it and ran it successfully.
- [x] `workflow_dispatch` authenticates through WIF without a service-account key.
- [x] A package-only push to `main` starts `Bump and Publish Packages` and, after it succeeds, `Deploy Publisher` (`f4a5b6b` → runs `39696122370` and `39696218691`).
- [x] The bot `[skip ci]` commit does not start a second publish or deploy.
- [x] Cloud Build reports `SUCCESS`; the image tags `sha-b651feb0dda9` (manual), `sha-a6e13834b61d` (automatic), and `sha-fb46b1cface7` (hardened) match their checked-out `analytics-engineering` commits.
- [x] The current Cloud Run revision `malloy-publisher-mcp-00031-2sd` is active at 100% traffic, and the routing assertion in `fb46b1c` was exercised successfully.
- [x] `/api/v0/status` reports `operationalState: serving` and lists `thelook_ecommerce`, `comics`, and `jaffle_shop`.
- [x] `malloy_getContext` returned `comics_explore` with model path `3_explores/comics_explore.malloy`; the environment lists both semantic packages.
- [x] Queries return the expected values through the deployed MCP endpoint: `Comic_Count: 3312`; `Order_Count: 686`; `Total_Revenue: 7226.67`. The earlier `Resource not found` response was an argument/path issue, not a routing defect.
- [x] The copied `publisher.json` versions match the versions in Credible at the time of deployment (`0.1.2`/`0.1.2`; later `comics@0.1.2`, `jaffle_shop@0.1.4`).
- [x] A failed Credible publish does not change the Cloud Run revision (run `39697920035` failed; deploy run `39698014901` skipped; revision stayed `00029-fzp`).
- [x] No secret, service-account key, `.env`, `.pem`, or generated package copy is committed.
- [x] The previous revisions `malloy-publisher-mcp-00030-z9m`, `00028-2nc`, and `00028-ric` and the relevant image digest are recorded in §9A.0.2.

### 9A.8 Decisions and remaining questions

1. **Trigger shape:** the separate `workflow_run` workflow was selected, created, and proven by both manual dispatch and a real package-only push.
2. **Wait for Credible readiness:** deploy as soon as publish succeeds. The copy uses Git source, so it does not wait for Credible's `buildStatus`.
3. **Storage permissions:** no new project-level storage role was needed because `malloy-analytics-user` already has `roles/owner`. A future cleanup should replace that broad role with the narrower build/deploy roles.
4. **Service account:** kept `malloy-analytics-user`, as confirmed. WIF uses both `roles/iam.workloadIdentityUser` and `roles/iam.serviceAccountTokenCreator`.
5. **`explores` migration:** keep the deprecated field and document the warning until a separate migration task.
6. **`thelook_ecommerce` and RAG:** leave the existing package and context pipeline unchanged.
7. **Traffic assertion:** `gcloud run deploy` can return success while traffic still points at the previous revision. The workflow now updates traffic explicitly and asserts `status.traffic[0].revisionName == status.latestCreatedRevisionName` before the smoke test.
8. **Generated package directory:** `workspace/semantic_layer/` is intentionally absent from the Publisher GitHub tree; it exists only in the CI build context and the image (§9A.0.1).







---

## 10. End-to-end acceptance checklist

> **Tag:** `GATE-10` | **Type:** acceptance gate | **Status:** `DONE` | **Exit gate:** §10.1–§10.4 | **Requires:** `TASK-07` and `TASK-09` (and `TASK-08` if enabled).

### 10.1 Repository

- [x] `semantic_layer/workspace/comics` exists with `publisher.json` and Malloy sources.
- [x] `semantic_layer/workspace/jaffle_shop` exists with `publisher.json` and Malloy sources.
- [x] `semantic_layer/publisher.config.json` exists for local Publisher.
- [x] `.github/workflows/deploy.yaml` watches `semantic_layer/workspace/**`.
- [x] `scripts/detect_changed_packages.py` recognizes `semantic_layer/workspace/`; a test against `HEAD~1..HEAD` reported both packages as `ALREADY_BUMPED`.
- [x] `scripts/cred_publish.sh` splits `semantic_layer/workspace/` paths correctly; the successful run published both packages.
- [x] No secret, `.env`, `.pem`, or generated package copy is committed.

### 10.2 Credible

- [x] `cred get environment demo` shows the expected environment (`demo`, `maxantipev`).
- [x] `motherduck` is listed in `cred ls connection` and is `INDEXED`.
- [x] `comics` and `jaffle_shop` are listed in `cred ls package` with `latestVersion: 0.1.1` and `indexStatus: indexed`.
- [x] The latest version of each package reaches `READY`; both versions report `buildStatus: READY`, `refusedSources: []`, and `stale: false`.
- [x] Queries work in the Credible App and use `motherduck`; re-verified on 2026-10-21 through the Credible Data API with `comics_explore -> Comic_Count = 3312` and `cafe_explore -> Order_Count = 686, Total_Revenue = 7226.67`.
- [x] The version bump commit `e55b110` is on `origin/main`.
- [x] The workflow did not republish an existing version; run `39508584228` published `0.1.1` once.

### 10.3 Publisher

- [x] Local Publisher serves both packages without `loadErrors`; the local startup line reports `packages=3 load_errors=0`, and the status endpoint lists `thelook_ecommerce`, `comics`, and `jaffle_shop`.
- [x] `workspace/semantic_layer/` is populated before `docker build`; `scripts/sync_semantic_layer.sh` completed and both `publisher.json` files were present.
- [x] The image contains both package directories; Cloud Build `2490ed3e-1a81-4140-a7f6-9a2d45da7158` succeeded after `COPY workspace/ ./workspace/`.
- [x] The deployed service reports `operationalState: serving`; revision `malloy-publisher-mcp-00028-ric`, 100% traffic.
- [x] Both packages are queryable in the deployed UI (verified through the deployed MCP query endpoint; the Cloud Run service exposes port 5050): `comics_explore -> 3312`, `cafe_explore -> 686 orders / 7226.67 revenue`.
- [x] The MCP context is updated if MCP coverage is required. It is not required for GATE-10: the RAG context intentionally covers only `thelook_ecommerce` until the compiler supports MotherDuck; Publisher's own MCP query tools serve both semantic packages.

### 10.4 Documentation

- [x] `6_PROJECT_1_Malloy_Semantic_Layer.md` §13 records the analysis.
- [x] This runbook reflects the actual package layout and the actual template adaptations.
- [x] The team knows which package is CI-owned and which, if any, is git-backed: both `comics` and `jaffle_shop` are CI-owned; neither is git-backed.
- [x] The team knows that a direct `cred publish` and a CI publish are equivalent uploads, not Git-backed publishing.

### 10.5 Acceptance evidence (2026-10-21)

| Check | Observed |
| :--- | :--- |
| Credible environment | `cred get environment demo` returned organization `maxantipev`, environment `demo`; `gitModelingEnabled: false` |
| MotherDuck connection | `cred ls connection` returned `motherduck`, `indexingStatus: INDEXED` |
| Credible packages | `comics` and `jaffle_shop` at `latestVersion: 0.1.1`, `indexStatus: indexed`, `autoPromote: true`, `warnings: []` |
| Credible versions | `buildStatus: READY`, `refusedSources: []`, `stale: false` for both |
| Credible query | Data API returned `[{"Comic_Count":3312}]` and `[{"Order_Count":686,"Total_Revenue":7226.67}]` |
| Workflow status | `39508584228`, conclusion `success`; only `0.1.1` published once |
| Publisher build | Cloud Build `2490ed3e-1a81-4140-a7f6-9a2d45da7158`, `SUCCESS` |
| Publisher revision | `malloy-publisher-mcp-00028-ric`, `Ready=True`, 100% traffic |
| Publisher status | `operationalState: serving`; `thelook_ecommerce`, `comics`, `jaffle_shop` |
| Publisher query | deployed MCP returned `Comic_Count: 3312` and `Order_Count: 686`, `Total_Revenue: 7226.67` |
| Local Publisher | `packages=3 load_errors=0`; status `serving`; both semantic packages listed |
| Manifest warning | `"explores" in publisher.json is deprecated`; expected and documented, not a load failure; migration deferred to a separate task |

---

## 11. Package ownership matrix

> **Tag:** `REF-11` | **Type:** decision record | **Status:** `DONE` | **Use:** fill before `TASK-08` and re-check at `GATE-10`.

Record the final decision before enabling both paths:

| Package | Canonical source | Publishing owner | Git-backed? | Publisher path |
| :--- | :--- | :--- | :--- | :--- |
| `comics` | `analytics-engineering/semantic_layer/workspace/comics` | CI/CD | No (unless separately enrolled) | `workspace/semantic_layer/comics` |
| `jaffle_shop` | `analytics-engineering/semantic_layer/workspace/jaffle_shop` | CI/CD | No (unless separately enrolled) | `workspace/semantic_layer/jaffle_shop` |

If a package is changed to git-backed ownership, update this table before the next merge. Do not run the CI publish job for a package that has become git-backed.

---

## 12. Known gaps and open items

> **Tag:** `REF-12` | **Type:** reference | **Status:** `N/A` | **Use:** review during every task; update if the facts change.

These are true as of 2026-10-21:

1. **`explores` is deprecated but still supported.** Both packages keep the field; see §9A.3. A future Publisher release that removes it is a breaking change.
2. **Publisher deployment automation is partially proven.** The `workflow_dispatch` path is executed and deployed; the automatic `workflow_run` path after a real package publish and the rollback rehearsal are still open.
3. **The Publisher RAG/MCP context is still built separately.** Publisher serves all three packages, but the build-time context index intentionally covers only `thelook_ecommerce` until the compiler supports `motherduck.table(...)`.
4. **Git-backed modeling is not enrolled.** `gitModelingEnabled` is `false`, all repository fields are `null`, and `gitRepositoryRegistered` is `false`.
5. **Git-backed enrollment is support-assisted.** Creating a repository and installing the App does not register it to the environment.
6. **The Credible workspace URL is not a repository URL.** `https://maxantipev.admin.credibledata.com/workspaces/workspace_demo` is a workspace page; it does not prove the environment is Git-backed.
7. **The status endpoint does not expose a top-level `loadErrors` field.** Use the startup `load_errors=0` line plus a real query for runtime verification.
8. **`TASK-09a` used the existing owner-level service account.** WIF, `GCP_WORKLOAD_IDENTITY_PROVIDER`, and `GCP_SERVICE_ACCOUNT` are configured, but `malloy-analytics-user` still has `roles/owner`; replacing it with the narrower build/deploy roles remains a cleanup item.
9. **The local Publisher `publisher_data` cache can mask a package change.** Start with `--init` when validating a new image or a new config; a stale cache reported `packages=0` during the 2026-10-21 check until the process was restarted.
10. **The Publisher `/api/v0/status` response serializes the MotherDuck access token.** The local status payload included `motherduckConnection.accessToken`; do not paste raw status output into logs, issues, or chat. Restrict or redact the endpoint before exposing it beyond the current trusted boundary.

---

## 13. Rollback and recovery

> **Tag:** `REF-13` | **Type:** recovery reference | **Status:** `N/A` | **Use:** only on failure; record the triggering task.

### 13.1 Disable CI publishing

If the workflow publishes incorrectly:

1. Disable the workflow in GitHub Actions:
   - **Actions → Bump and Publish Packages → ⋯ → Disable workflow**.
2. Re-pin the last known good version:

```bash
cred update package comics --version <last-good-version>
cred update package jaffle_shop --version <last-good-version>
```

3. Fix the package or workflow in a feature branch.
4. Re-enable the workflow only after a successful local dry run.

### 13.2 Disable git-backed modeling

Only after confirming the behavior with Credible support:

```bash
cred update environment demo --git-modeling false -y
```

This stops new git-backed drafts. It may not convert existing git-backed packages back to CI ownership. Do not assume that disabling the flag restores direct publishing for a package that has already published through a merge.

### 13.3 Recover the Publisher

If a bad sync removes packages from the image:

1. Re-run `./scripts/sync_semantic_layer.sh` with a known-good checkout.
2. Rebuild the image.
3. Deploy the previous Cloud Run revision if the image is already broken:

```bash
gcloud run revisions list \
  --service malloy-publisher-mcp \
  --region northamerica-northeast1

gcloud run services update-traffic malloy-publisher-mcp \
  --region northamerica-northeast1 \
  --to-revisions <previous-revision>=100
```

### 13.4 Rotate credentials

- **Credible token:** create a new group access token, update `CRED_JWT`, delete the old token, and run a no-op publish test.
- **GitHub App private key:** generate a new key, update `CICD_BOT_APP_PRIVATE_KEY`, delete the old key, and run a no-op workflow test.
- **Mirror token:** rotate `SEMANTIC_LAYER_MIRROR_TOKEN` and `PUBLISHER_DISPATCH_TOKEN` on the same schedule.
- **MotherDuck token:** rotate in MotherDuck, update the Credible connection, the local `.env`, and the Cloud Run secret.

Never rotate by committing a new value. Update the secret store first, then restart or redeploy the consumer.

---

## 14. Reference commands

> **Tag:** `REF-14` | **Type:** reference | **Status:** `N/A` | **Use:** command lookup only; no task completion by itself.

```bash
# Environment and packages
cred status
cred get environment demo
cred ls package
cred get package comics
cred get version comics <versionId>
cred ls connection

# Publishing from a package directory
cd semantic_layer/workspace/comics
cred publish --dry-run
cred publish --set-latest --yes

# Local Publisher
npx --yes @malloy-publisher/server@0.0.244 \
  --server_root ./workspace-local \
  --config ./workspace-local/publisher.config.json \
  --port 4000 \
  --init \
  --watch-env workspace

# Verify the Publisher
curl -fsS http://localhost:4000/api/v0/status | jq

# GitHub Actions
gh run list --workflow deploy.yaml --limit 5
gh run watch
```

For the official references, see:

- Credible CLI: <https://www.credibledata.com/docs/platform-admin/cli>
- Credible CI/CD: <https://www.credibledata.com/docs/platform-admin/cicd>
- Credible git-backed modeling: <https://www.credibledata.com/docs/how-to/modeling/git-backed-modeling>
- CI/CD template: <https://github.com/credibledata/credible-cicd-template>
- Publisher deployment: [`analytics-malloy-publisher-rag/DEPLOYMENT.md`](../../../analytics-malloy-publisher-rag/DEPLOYMENT.md)