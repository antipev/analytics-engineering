# Project 1 — RAG context coverage for every served Publisher package

> **Date:** 2026-10-28 (Phase 4 verified 2026-10-29)
> **Status:** **Phase 4 complete — the project is done.** Phase 0 **applied and validated**; **Phase 1 complete** — `GATE-01` **PASS** (repo truth `3/3`). **Phase 2 complete** — `TASK-04`, `TASK-05`; `GATE-02` PASS at command level, container half still blocked on a Docker daemon here. **Phase 3 complete** — `GATE-03` **PASS** on the third run (`malloy-publisher-mcp-00035-tqq`). **Phase 4 complete** — `TASK-09`…`TASK-13` done and `GATE-04` **PASS** (`malloy-publisher-mcp-00037-ct6`) with the coverage gate armed (`ENFORCE_CONTEXT_COVERAGE: true`, `3/3`), the startup probe asserted on `/context/healthz`, the uptime check and alert live, the build context down to 133.6 MiB, and a cold session returning 3 sections plus the money measures for all three packages. `GATE-04` also found and fixed one more real defect (a stale domain context advertising an explore that no longer exists) and left one open finding (`OPEN-1`, model-path resolution in the relayed `malloy_executeQuery`).
> **Related:** [`6_PROJECT_1_Malloy_Semantic_Layer.md`](./6_PROJECT_1_Malloy_Semantic_Layer.md) — the semantic layer this context is built from. [`7_PROJECT_1_Credible_GitHub_Implementation.md`](./7_PROJECT_1_Credible_GitHub_Implementation.md) §9A — the Publisher publish automation. [`10_PROJECT_1_Dagster_CI_Deployment.md`](./10_PROJECT_1_Dagster_CI_Deployment.md) — the deployment pattern and task-tracking style reused here.
> **Goal:** `malloy_getContext` returns a real 3-section RAG context, with the money measures, for **all three** served packages (`thelook_ecommerce`, `jaffle_shop`, `comics`) — and the deploy fails loudly if that ever regresses.
> **Change budget:** one connection block in one JS file, one Dockerfile `RUN` line, one renamed route, one CI build step, one IAM binding, one repository variable. **No new services, no new repositories, no copies of the semantic layer.**

---

## 0. TL;DR

| # | Question | Answer |
|---|---|---|
| 1 | Why do `jaffle_shop` and `comics` return a key-only stub from `malloy_getContext`? | The Node Publisher **serves** all three packages, but the RAG index has a graph for **only** `thelook_ecommerce`. Stage 3 finds no graph, logs nothing, and silently relays the call to the Node upstream, which answers with the raw exploration surface — fields, no joined measures. |
| 2 | Why is the graph missing? | Two reasons stacked: (a) the image builds the index against `publisher.context.config.json`, which lists **only** `thelook_ecommerce`; (b) even if it were listed, the build-time Malloy compiler has **no MotherDuck connection**, so `jaffle_shop`/`comics` cannot compile. |
| 3 | Is the semantic layer missing from the RAG repo? | **No.** `workspace/semantic_layer/{jaffle_shop,comics}` exists on disk and is recreated on every build by `scripts/sync_semantic_layer.sh`; it is **git-ignored on purpose**. GitHub showing only `thelook_ecommerce` is correct, not a bug. `run_context_pipeline.py --list` proves all three packages are visible inside the checkout. |
| 4 | Can it be fixed without a new npm package? | **Yes.** `@malloydata/db-duckdb@0.0.433` (already in `context/node_modules`) supports `DuckDBConnection({databasePath:'md:<database>', motherDuckToken})`. Proven live: `jaffle_shop` compiles and queries `Total_Revenue=7226.67`, `Gross_Margin=5820.95`, `Order_Count=686`; `comics` queries `Comic_Count=3312`. `@malloydata/db-motherduck` does not exist on npm. |
| 5 | Why did nobody notice? | Nothing ever measured it. The deploy smoke test only checks that `/api/v0/status` lists the packages and that `loadErrors` is empty — both true even when every RAG context is empty. Phase 0 adds the missing measurement. |
| 6 | Two hidden blockers? | The deploy identity **cannot read** `motherduck-token`, and `/healthz` is **swallowed by the Google edge**. Both are diagnosed in §5 and §6 with a quick fix and a long-term fix. |


---

## 1. Symptom and evidence

### 1.1 What the agent sees

`malloy_getContext` for `thelook_ecommerce` returns ~19 KB of three-section context. For `jaffle_shop` and `comics` it returns a bridge exploration with **14 fields and zero measures** — everything is a key. The money measures do exist, but on the joined entities (`cafe_orders.Total_Revenue`, `order_items.Total_Revenue`, …), so an agent that only reads the root surface concludes the model has no money in it.

### 1.2 Live measurement of the deployed service

`scripts/verify_context_coverage.py` (added in Phase 0) against revision `malloy-publisher-mcp-00034-n7p`:

```
DEPLOYED RAG CONTEXT COVERAGE  (https://malloy-publisher-mcp-bolcwt6srq-nn.a.run.app)
✅  workspace/thelook_ecommerce     19507 chars  3-section context returned
❌  workspace/comics                    0 chars  empty executableContext (package has no RAG graph)
❌  workspace/jaffle_shop               0 chars  empty executableContext (package has no RAG graph)
1/3 served package(s) return a real RAG context.                    exit 1
```

### 1.3 Live measurement of the repository

`context/orchestration/verify_index_coverage.py` (added in Phase 0) against `workspace/publisher.config.json`:

```
❌ workspace__thelook_ecommerce  -> missing Stage-2 graph (step_2_workspace__thelook_ecommerce_rag_intent_graph.json)
   ⚠️  domain context missing (Path A routing quality degraded)
❌ workspace__comics             -> missing Stage-2 graph
❌ workspace__jaffle_shop        -> missing Stage-2 graph
0/3 served package(s) have a RAG context.                            exit 1
```

`thelook_ecommerce` shows as missing locally because the committed files are still named `step_*_theLook-DEMO__thelook_ecommerce_*`; the image rebuilds them under the `workspace__` names. The two failing packages fail in **both** places, which is the real finding.

> **This is the "before" state.** After `TASK-03` rebuilt the graphs, the same command on the same config prints `✅` for all three and `3/3 served package(s) have a RAG context.` / `exit 0` (see §7 `TASK-03` record).

### 1.4 What the publisher serves

Reachable, healthy, and complete: `GET /` 200, `GET /openapi.json` 200, `GET /api/v0/status` 200 (all three environments, `loadErrors` empty), `POST /mcp` 200 with `malloy_executeQuery` + `malloy_getContext` listed. The package layer is fine; only the context layer is empty.

---

## 2. Root cause

```
analytics-engineering/semantic_layer/workspace/{jaffle_shop,comics}/**.malloy
        │  (CI: scripts/sync_semantic_layer.sh — build time, git-ignored destination)
        ▼
publisher/workspace/semantic_layer/{jaffle_shop,comics}/    ← present on disk, absent from GitHub by design
        │
        ├──► Node Publisher (publisher.config.json)  ──► serves 3 packages   ✅
        │
        └──► RAG pipeline (publisher.context.config.json) ──► serves 1 package   ❌
                     │
                     ├─ blocker (a): the config lists only thelook_ecommerce
                     └─ blocker (b): the compiler has no MotherDuck connection,
                                     so these two cannot compile even if listed
                     ▼
             context/data/step_2_*.json missing  ──►  context/chroma_db empty for these ids
                     ▼
             Stage 3: no graph → silent relay to Node  ──►  key-only stub  ──►  agent blindness
```

Five conditions had to line up for the failure to be invisible, and each one is a separate defect:

| ID | Defect | Consequence |
|---|---|---|
| D1 | `publisher.context.config.json` excludes two served packages | no graph, no vectors |
| D2 | Build-time compiler has no `motherduck` connection | models un-compilable in the image build |
| D3 | Stage 3 relays silently when a graph is missing | failure looks like a *shallow model*, not a *broken index* |
| D4 | `run_context_pipeline.py` called `delete_collection()` | any second indexing run erased the whole collection (fixed in Phase 0) |
| D5 | Smoke test asserts package *listing*, never context *content* | deploy stays green while agents are blind |

---

## 3. Phase 0 — already applied (observability first, no behaviour change)

Observation had to land before repair: without it, every later change is unverifiable. These five files are in the working tree now, uncommitted, and each one was exercised.

| File | Repo | Status | Purpose | Validation performed |
|---|---|---|---|---|
| `context/orchestration/verify_index_coverage.py` | publisher-rag | **new**, 7.3 KB | Is there a Stage-2 graph *and* a domain context for every package we serve? `--soft`, `--json`, `--require pkg:Measure` | ran on the live config: `0/3`, exit 1; `--soft` exit 0; `--json` parses |
| `scripts/verify_context_coverage.py` | publisher-rag | **new**, 6.5 KB, stdlib only | Asks a *deployed* service for `malloy_getContext` per package; fails on empty/short context or a missing required measure | ran against the live revision: `1/3`, exit 1 / `--soft` exit 0 |
| `context/orchestration/run_context_pipeline.py` | publisher-rag | +20/−6 | Chroma indexing is now per-context (`delete(where={"context": …})`) instead of `delete_collection()` | `--list` discovers all 3 packages |
| `context/step_3_mcp_server/step_3_mcp_dual_pathway_server.py` | publisher-rag | +52/−6 | (1) warns per package at boot which packages will relay, (2) warns on each silent relay, (3) `/healthz` reports `contexts_expected` / `contexts_indexed` / `indexed[]` / `missing[]` | coverage function executed against the real helpers: `3 expected, 0 indexed, 3 missing`, TTL cache consistent |
| `.github/workflows/deploy-publisher.yml` | analytics-engineering | +26 | 11th step "Verify RAG context coverage for every served package" — **warn-only** until `ENFORCE_CONTEXT_COVERAGE=true` | `yaml.safe_load` OK, 11 steps, last step correct |

Design notes:

- **Warn-only by default.** Shipping a hard gate before the index exists would break every deploy. The gate is armed by a repository variable, which is `TASK-09`.
- **The gate asserts a measure, not a byte count.** `--require jaffle_shop:Revenue` compares normalized names (`_`, space, case-insensitive), because the index stores qualified names like `order_items.Total_Revenue`.
- **`/healthz` is a bonus, not a dependency.** The deploy step does not use it — correct decision, see §6.
- **Nothing is committed yet.** `git status` in both repos shows exactly these files and nothing else.


---

## 4. The repair plan — five changes, four files

### Change 1 — teach the compiler MotherDuck (`step_1_compile_malloy.js`, ~6 lines)

The evidence that fixes the shape of this change — every source in both packages names the connection **`motherduck`** explicitly:

```malloy
// workspace/semantic_layer/jaffle_shop/1_raw_views/config.malloy
source: cafe_customers_raw is motherduck.table('marts.cafe_customers')
// workspace/semantic_layer/comics/1_raw_views/config.malloy
source: comics_raw is motherduck.table('marts.comics')
```

`context/step_1_extract/step_1_compile_malloy.js` originally built a `FixedConnectionMap` with exactly two entries (`duckdb`, `bigquery`). **Applied** (lines 125-153): a third, conditional entry.

```js
const connectionEntries = [
  ['duckdb', duckdbConn],
  ['bigquery', bigqueryConn],
];

// The database name matches workspace/publisher.config.json
// (motherduckConnection.database) and can be overridden for a different env.
const motherduckToken = process.env.MOTHERDUCK_TOKEN;
if (motherduckToken) {
  const motherduckDatabase = process.env.MOTHERDUCK_DATABASE || 'data_warehouse_demo';
  connectionEntries.push(['motherduck', new DuckDBConnection({
    name: 'motherduck',
    databasePath: `md:${motherduckDatabase}`,
    motherDuckToken: motherduckToken,
  })]);
}
const connectionMap = new FixedConnectionMap(new Map(connectionEntries), 'duckdb');
```

- `DuckDBConnectionOptions` (`@malloydata/db-duckdb/dist/duckdb_connection.d.ts:8`) is `{ name, databasePath?, motherDuckToken? }` — no new package. Installed version: 0.0.433. The token is wired to DuckDB's own `motherduck_token` setting (`duckdb_connection.js:184`), so it also works through the `ATTACH`/`setup()` path rather than only as a bare `md:` URI credential.
- **`md:` alone is not enough** (found live, first attempt): `databasePath: 'md:'` opens MotherDuck with no default catalogue, so `marts.cafe_customers` fails with `Catalog Error: Table with name "marts.cafe_customers" does not exist because schema "marts" does not exist`. The database must be named in the path — `md:data_warehouse_demo` — which is why the name is taken from `publisher.config.json` (with `MOTHERDUCK_DATABASE` as the override for a second environment).
- Without the token the connection map is exactly today's two entries. Verified by hashing the compiler output of `thelook_ecommerce` (which never references `motherduck`) across three runs — `HEAD` script, patched script with token, patched script without token: identical `sha256 c946c8de…`, 65 788 bytes each.
- The `workingDirectory` argument used by the `duckdb` entry is not needed here: `md:` is a remote catalogue and the sources are fully qualified (`marts.…`).

### Change 2 — build the index where a token exists (`scripts/build_context_index.sh` + one workflow step)

CI, not the image build, is the right place: the token is already a GitHub/Secret Manager asset, the index is data not code, and building it in CI keeps `docker build` reproducible and fast.

```
scripts/build_context_index.sh      # new, ~40 lines
  ├─ preflight: gcloud secrets versions access latest --secret=motherduck-token >/dev/null   (fail in 3 s, legibly)
  ├─ cd context && npm ci --omit=dev
  ├─ python3 context/orchestration/run_context_pipeline.py \
  │        --all --index-chroma --config workspace/publisher.config.json     # NOT --fresh
  └─ python3 context/orchestration/verify_index_coverage.py \
             --config workspace/publisher.config.json --require jaffle_shop:Revenue
```

Called from `deploy-publisher.yml` after `sync_semantic_layer.sh` and before `gcloud builds submit`, so the generated `context/data/*` and `context/chroma_db/*` are inside the build context. `.gcloudignore` already excludes `context/chroma_db/` from the upload — therefore the graphs (`context/data/*.json`) travel and the vectors are re-created at image build from those graphs (Change 3). That is deliberate: vectors are cheap to rebuild from graphs, and shipping them makes the image stale.

### Change 3 — the image must not erase what CI built (`Dockerfile`, 1 line)

Current line:

```
RUN python3 /app/context/orchestration/run_context_pipeline.py --all --fresh --index-chroma \
      --config /app/workspace/publisher.context.config.json
```

`--fresh` regenerates and **overwrites** the curated graphs, and the narrow config drops two packages. Replace with an idempotent form:

```
RUN python3 /app/context/orchestration/verify_index_coverage.py --soft --config /app/workspace/publisher.config.json \
 && python3 /app/context/orchestration/run_context_pipeline.py --all --index-chroma \
      --config /app/workspace/publisher.config.json
```

No `--fresh`: existing graphs are reused, missing ones are built, Chroma is re-indexed from whatever graphs are present.

**Correction, measured while doing `TASK-04`:** the first draft of this paragraph claimed "plain `docker build` (no CI) still produces a working image — it simply produces `thelook_ecommerce` only". That is **false**, and the build must not be written as if it were true: `run_context_pipeline.py:242-253` validates *every* package in the config and `sys.exit(1)`s on the first compile failure, and `step1.extract_context()` re-compiles unconditionally (`compile_package_explores`, `step_1_python_context_retrieval_script.py:280`) — `fresh=False` only preserves the curated *domain context*, it does not skip the compile. With `publisher.config.json` that means `jaffle_shop`/`comics` (MotherDuck-only) make the image build **require `MOTHERDUCK_TOKEN`**, whether or not graphs already exist. Measured: with graphs present and no token, the build step still exits 1 with 11 compile errors; with a token, all three cases in the `TASK-04` record pass. So the token is passed to the build as a build arg (`ARG MOTHERDUCK_TOKEN`, never an `ENV`, so it lands in no layer) and **`TASK-08` must supply it to `gcloud builds submit` via a `cloudbuild.yaml` `buildArgs` block** — `--tag` alone cannot carry build args. This also means an image that would answer `malloy_getContext` without money measures is now *unbuildable*: the `RUN` line ends in a hard `verify_index_coverage.py` after the pipeline, which is a stronger guarantee than the advisory `--soft` pre-check alone.

### Change 4 — stop maintaining two configs (`publisher.context.config.json`)

`publisher.context.config.json` exists solely because the image build could not reach MotherDuck. Once Change 1 lands, that reason is gone. Retarget every reference to `publisher.config.json` and delete the file; the two-config split is how D1 happened in the first place.

### Change 5 — arm the gate (2 lines in `deploy-publisher.yml`)

Export `MOTHERDUCK_TOKEN` to the index step (secret, §5), then set repository variable `ENFORCE_CONTEXT_COVERAGE=true` so the Phase-0 step stops being advisory.


---

## 5. Blocker A — the deploy identity cannot read `motherduck-token`

### 5.1 Measured facts (not assumptions)

```
$ gcloud secrets get-iam-policy motherduck-token --project my-1-st-project-training
roles/secretmanager.secretAccessor →
    serviceAccount:669258319971-compute@developer.gserviceaccount.com   # Cloud Run runtime SA  ✔
    serviceAccount:669258319971@cloudbuild.gserviceaccount.com          # Cloud Build           ✔
    (malloy-analytics-user@… is NOT in the list)

$ gcloud iam service-accounts get-iam-policy malloy-analytics-user@…
roles/iam.workloadIdentityUser → principalSet://iam.googleapis.com/projects/669258319971/
                                 locations/global/workloadIdentityPools/github-pool/
                                 attribute.repository/antipev/analytics-engineering

$ gcloud run services describe malloy-publisher-mcp --region northamerica-northeast1
spec.template.spec.serviceAccountName = 669258319971-compute@developer.gserviceaccount.com
status.latestReadyRevisionName        = malloy-publisher-mcp-00034-n7p

$ gh secret list
CICD_BOT_APP_ID · CICD_BOT_APP_PRIVATE_KEY · CRED_JWT · GCP_SERVICE_ACCOUNT · GCP_WORKLOAD_IDENTITY_PROVIDER
(no MOTHERDUCK_TOKEN)
```

Reading:

1. The **runtime** is fine — `--set-secrets=MOTHERDUCK_TOKEN=motherduck-token:latest` works because the Cloud Run service runs as the compute SA, which holds `secretAccessor`. This is why the deployed container can query MotherDuck today.
2. The **CI deployer** is `malloy-analytics-user@`, impersonated through `github-pool` and locked to `attribute.repository/antipev/analytics-engineering`. It has **no** access to the secret.
3. The WIF condition names **one repository**. The publisher-rag repo cannot authenticate to GCP at all. **Consequence: the index build must live in `analytics-engineering`'s workflow** — which is what Change 2 does. This is a constraint, not a preference.

### 5.2 Quick fix (2 minutes, one command)

Grant the existing deploy identity read access on that one secret:

```bash
gcloud secrets add-iam-policy-binding motherduck-token \
  --project my-1-st-project-training \
  --member serviceAccount:malloy-analytics-user@my-1-st-project-training.iam.gserviceaccount.com \
  --role roles/secretmanager.secretAccessor
```

Then, in the workflow, read the value at run time rather than copying it into a second store:

```yaml
- name: Resolve MotherDuck token
  run: |
    TOKEN=$(gcloud secrets versions access latest --secret=motherduck-token --project "$PROJECT_ID")
    echo "::add-mask::$TOKEN"
    echo "MOTHERDUCK_TOKEN=$TOKEN" >> "$GITHUB_ENV"
```

Alternative quick fix, zero IAM change: add GitHub repo secret `MOTHERDUCK_TOKEN` and use `${{ secrets.MOTHERDUCK_TOKEN }}`.

**Why the Secret Manager route is preferable even as a quick fix:** one source of truth. A GitHub secret is a silent copy that goes stale the day the token is rotated; the `--set-secrets` path used by the service already reads Secret Manager, so one rotation keeps both paths working.

### 5.3 Long-term fix (≈30 minutes, one PR)

| Step | Change | Why it survives rotation and personnel change |
|---|---|---|
| 1 | Create a dedicated `malloy-ci-indexer@my-1-st-project-training.iam.gserviceaccount.com` | The deployer identity is `roles/owner`; an indexing job that reads a warehouse token and writes build artifacts should not inherit that |
| 2 | Grant it **only**: `secretmanager.secretAccessor` on `motherduck-token`, `logging.logWriter`, `artifactregistry.writer` (if the image path needs it) | least privilege, auditable |
| 3 | Add `attribute.repository/antipev/analytics-engineering` for that SA in `github-pool` | same guard as today: only this repo can impersonate |
| 4 | Use it **only** in the index step (`google-github-actions/auth` accepts a per-step `service_account`) | the deploy keeps its own identity; no privilege creep |
| 5 | Keep `--set-secrets` on the service pointing at the same secret version | one rotation, both consumers |
| 6 | Set a calendar reminder for token rotation; document it in `DEPLOY.md` | the token will expire eventually |

**Guard rail that makes both fixes safe:** the preflight in `build_context_index.sh` (§4, Change 2). Without it, a missing binding surfaces as a Malloy compile error 4 minutes into a deploy; with it, the run stops in 3 seconds saying *"cannot read secret motherduck-token as malloy-analytics-user@ — run this gcloud command"*.

### 5.4 Acceptance

```bash
gcloud secrets versions access latest --secret=motherduck-token --project my-1-st-project-training >/dev/null && echo OK
```
run **as the CI identity** (or observed green in a workflow run) — not as your own user, which is why this failure was invisible locally.


---

## 6. Blocker B — `/healthz` is swallowed by the Google edge

### 6.1 Measurement

The service is healthy on every other path, and `/healthz` alone returns Google's own error page:

| Path | Status | Body |
|---|---|---|
| `/` | 200 | app HTML |
| `/openapi.json` | 200 | FastAPI schema |
| `/docs` | 200 | Swagger UI |
| `/api/v0/status` | 200 | publisher JSON, 3 environments |
| `POST /mcp` | 200 | JSON-RPC result |
| **`/healthz`** | **404** | `<!DOCTYPE html><html lang=en> … <title>Error 404 (Not Found)!!1</title>` (1568 bytes, `referrer-policy: no-referrer`) |
| `/healthz/` | 200 | reaches the app (trailing slash) |
| `/healthz?x=1` | 404 | still swallowed |
| `/healthz2`, `/xhealthz`, `/readyz`, `/livez`, `/ping` | 200 | reach the app |
| `/health` | 200 | **Node** actuator JSON (`{"status":"UP","components":…}`), proxied by the Python catch-all |

Decisive control: the **same path on a different service** in the same project returns the identical Google 404 page.

```
$ curl -o /dev/null -w '%{http_code}' https://analytics-dagster-bolcwt6srq-nn.a.run.app/healthz
404    ← body is byte-for-byte the same GFE error page
```

`analytics-dagster` is a different container with a different app and no `/healthz` route of its own. So this is **not** an application routing bug and not a FastAPI bug: the exact path `/healthz` is intercepted by Google Frontend before the request reaches the container. Variants (`/healthz/`, `/healthz2`) prove the rule is exact-path, not prefix — which is why the route "exists in OpenAPI but not on the internet".

### 6.2 Consequence for this project

Nothing in the repair depends on `/healthz`, so the deploy gate does not block on it. But the new coverage payload (`contexts_expected`, `contexts_indexed`, `missing[]`) is currently unreachable from outside, which wastes the most useful signal we just built.

### 6.3 Quick fix (10 minutes, 1 file)

Move our endpoint off the reserved name and keep a back-compatible alias:

```python
@app.get("/context/healthz")      # external, monitored path — not reserved by GFE
@app.get("/healthz")              # alias, works on 127.0.0.1 / docker run / Cloud Run probes
async def healthz(): ...
```

Two rules for whoever does this:

- **Do not rename to `/health`.** That path already returns the Node publisher's actuator through the catch-all proxy; taking it over would silently change what any existing monitor sees.
- Keep the alias registered *before* `@app.api_route("/{full_path:path}")` (currently the last route in the file) so it is not proxied to Node.

### 6.4 Long-term fix (≈45 minutes, prevents the whole class of bug)

| Layer | Change | Benefit |
|---|---|---|
| Path hygiene | All app-owned operational endpoints live under one prefix (`/context/*`). Document the reserved list (`/healthz`, `/_ah/*`, `/favicon.ico` behaviour) in `DEPLOY.md` | nobody re-introduces a squatted path |
| Cloud Run probe | Add `--startup-probe` on `/context/healthz` (`initialDelaySeconds=5, periodSeconds=5, failureThreshold=24`) | traffic is only routed once Stage 3 is really serving; the 60 s Node-MCP wait in `entrypoint.sh` stops racing the first request |
| Monitoring | Cloud Monitoring uptime check on `/context/healthz`, alert on `contexts_indexed < contexts_expected` | the exact failure of this document becomes a page instead of a support ticket |
| Deploy gate | `deploy-publisher.yml` asserts the JSON from `/context/healthz` — `contexts_indexed == contexts_expected` and `missing[]` empty | one check that covers *every* package forever, complementary to the per-measure `--require` assertions |

The startup probe is also the cheapest reliability win available: today the container can report the revision ready while the Python process is still loading Chroma.

### 6.5 Acceptance

```bash
curl -sS https://<service>/context/healthz | python3 -m json.tool
# { "status": "ok", "contexts_expected": 3, "contexts_indexed": 3, "indexed": [...], "missing": [] }
```


---

## 7. Execution split — 13 tasks, 5 gates

Each task is independently reviewable and independently revertable. `GATE-n` is an observation of production, not a build step: it is the point at which the work is accepted or sent back. Statuses: `TODO` · `IN PROGRESS` · `DONE` · `BLOCKED`.

### Phase 1 — make the two packages compilable (RAG repo, local, no CI)

| ID | Task | Files | Acceptance | Effort | Status |
|---|---|---|---|---|---|
| `TASK-01` | Add the conditional `motherduck` connection to the Stage-1 compiler | `context/step_1_extract/step_1_compile_malloy.js` | With `MOTHERDUCK_TOKEN` unset the compiler behaviour is unchanged (same error string for `jaffle_shop`, identical output hashes for `thelook_ecommerce`); with it set, `motherduck` is registered and both semantic-layer packages compile | 15 m | `DONE` |
| `TASK-02` | Prove compilation locally for both packages | — | `step_1` on `jaffle_shop` and `comics` exits 0 and writes `step_1_*.json`; `jaffle_shop` carries `Total_Revenue`/`Gross_Margin`/`Order_Count` (33 measures), `comics` carries `Comic_Count`/`Comics_With_News` (8 measures) | 15 m | `DONE` |
| `TASK-03` | Build the graphs and the index locally, without `--fresh` | — | `verify_index_coverage.py --config workspace/publisher.config.json` → `3/3`; Chroma holds exactly 3 context ids (`--list`-style check or the healthz payload). **Prereq:** scratch venv with `context/orchestration/requirements.txt` (chromadb, fastapi, uvicorn, httpx) — the pipeline imports Stage 3 even for a Stage-1/2-only run | 20 m | `DONE` |

**`GATE-01` — local end-to-end:** start Stage 3 locally against the rebuilt index and call `malloy_getContext` for `jaffle_shop`; the answer must contain `Total_Revenue` and a three-section body (not the 14-field bridge).

#### `TASK-01` record (2026-10-28, applied, uncommitted)

| Check | Command | Result |
|---|---|---|
| Syntax | `node --check context/step_1_extract/step_1_compile_malloy.js` | `syntax OK` |
| No token → unchanged failure | `env -u MOTHERDUCK_TOKEN node …cafe_explore.malloy` | exit 1, `error` string **identical** to the pre-change run (JSON `error` field compares equal; only stack line numbers shift 139→158) |
| No regression on the package that ignores MotherDuck | `thelook_ecommerce` compiled by `HEAD` script / patched + token / patched − token | all three `sha256 c946c8de…`, 65 788 bytes |
| `jaffle_shop` compiles | patched script + real token | exit 0, 28 807 bytes JSON, `cafe_explore` = 95 fields / 33 measures / 3 joined entities, 2.5 s |
| `comics` compiles | patched script + real token | exit 0, 29 319 bytes JSON, `comics_explore` = 108 fields / 8 measures, 2.9 s |
| Measures evaluate on real data | `Runtime` + `run: cafe_explore -> { aggregate: Total_Revenue, Gross_Margin, Order_Count }` | `7226.67 / 5820.95 / 686` — exactly the GATE-01 numbers |
| `comics` evaluates | `run: comics_explore -> { aggregate: Comic_Count, Comics_With_News }` | `3312 / 3312` |

Two API details worth keeping: `new Runtime({ urlReader, connections })` — **`connections`**, not `connectionMap` (this Malloy version rejects the latter with *"A MalloyConfig, LookupConnection<Connection>, or Connection is required"*); and results are read as `(await result.data).toObject()`, not `result.toObject()`.

#### `TASK-02` record (2026-10-28, applied, uncommitted)

Acceptance is met through the real Stage-1 entry point, not the JS compiler directly:

| Check | Command | Result |
|---|---|---|
| Stage 1, `jaffle_shop` | `python3 context/step_1_extract/step_1_python_context_retrieval_script.py --context workspace__jaffle_shop` | exit 0, 4.0 s → `step_1_workspace__jaffle_shop_raw_extracted.json` (42 867 B, 1 source, **95 fields / 33 measures**), `…_domain_context.json` (**4 intents**) |
| Stage 1, `comics` | same with `--context workspace__comics` | exit 0, 2.5 s → 45 235 B, **108 fields / 8 measures**, **2 intents** |
| Whole-package compile, with token | `validate_package()` for both packages (the check `run_context_pipeline.py:243` runs before anything else) | **`OK workspace__comics` (4 files), `OK workspace__jaffle_shop` (8 files)** — exit 0, 37.5 s total ≈ 3.1 s/file |
| Whole-package compile, no token | same driver with `env -u MOTHERDUCK_TOKEN` | **`FAIL` for both, exactly 12 "Error(s) compiling model" lines (8 + 4), exit 1** → the compiler is genuinely the thing under test |
| `thelook_ecommerce` unaffected | `step_1` output compiled by `HEAD` vs patched script | identical `sha256 c946c8de…` (see `TASK-01` record) |

Three findings, each of which changes a later task:

1. **`run_context_pipeline.py` imports Stage 3 unconditionally** (`line 68`, inside `run_one_package`), so *any* pipeline run — even one that never touches Chroma — dies with `ModuleNotFoundError: No module named 'fastapi'` unless `context/orchestration/requirements.txt` is installed. `TASK-03` needs a scratch venv for that; **`TASK-07`'s CI script must install those 4 packages** (or run inside the image) or the index build will fail before it starts.
2. `prune_orphaned_artifacts()` matches by *substring* of an active `context_id`, so the first pipeline run deleted the stale `step_*_theLook-DEMO__thelook_ecommerce_*.json` artifacts (old env-name prefix, none matching `workspace__thelook_ecommerce`). Harmless — `TASK-03` rebuilds all three — but it means `context/data/` now holds only the two new packages, which is why `verify_index_coverage.py` will report `2/3` until `thelook_ecommerce` is rebuilt. Those three deletions are **tracked** files, so they appear in `git status` and belong to `TASK-03`'s commit.
3. **`context/chroma_db/` is tracked in git (85 files, 9.4 MB) while `.gcloudignore:20` excludes it from Cloud Build.** So Cloud Build never sees the committed index (the image rebuilds it at `Dockerfile:39`), but a *local* `docker build` copies it in and then `--fresh` deletes it — the image you build locally is not the image CI builds. Consequence for `TASK-03`: rebuilding the index locally rewrites 85 tracked binaries, a 9 MB diff that carries no reviewable information. Recommendation, folded into `TASK-12`: `git rm -r --cached context/chroma_db` + add it to `.gitignore` (it is already `.gcloudignore`d, and after Change 2 CI owns the index), so the artifact stops being a 9 MB binary diff on every rebuild.

**Measured, and carried into later tasks:** the local `docker build` path and the Cloud Build path have *different inputs* for `chroma_db`; `TASK-04`'s idempotent build must therefore work both with the directory present (local) and absent (CI) — i.e. "portable copy or build if missing", never a bare `COPY` that assumes one of the two.

Measured compile cost for the risk table: **≈3.1 s per `.malloy` file**, 12 files today, 3 packages after `TASK-03` ⇒ validation ≈40 s, full Stage-1 for 3 packages ≈15 s. Well inside the "~4 min" threshold, so the Docker-side build stays viable.

#### `TASK-03` record (2026-10-28, applied, uncommitted)

Run through the real entry point, from a scratch venv, **without `--fresh`**:

```bash
python3 -m venv /tmp/ragvenv && /tmp/ragvenv/bin/pip install -r context/orchestration/requirements.txt
export MOTHERDUCK_TOKEN="$(gcloud secrets versions access latest --secret=motherduck-token …)"
/tmp/ragvenv/bin/python context/orchestration/run_context_pipeline.py --all --index-chroma
```

| Check | Result |
|---|---|
| Whole-package validation (runs first, `run_context_pipeline.py:243`) | `OK workspace__thelook_ecommerce`, `OK workspace__comics`, `OK workspace__jaffle_shop` |
| Stage 1 + Stage 2, `thelook_ecommerce` | 205 chunks, router loads 10 intents / 10 entities / **185 metrics** |
| Stage 1 + Stage 2, `comics` | 112 chunks, router loads 2 intents / 2 entities / **108 metrics** |
| Stage 1 + Stage 2, `jaffle_shop` | 103 chunks, router loads 4 intents / 4 entities / **95 metrics** |
| Curated domain contexts survive | `jaffle_shop` and `comics` printed *"Domain context already present; keeping curated …"* — i.e. `--fresh` was **not** used, as required. `thelook_ecommerce`'s domain file had been pruned, so it was auto-derived (10 intents) |
| Chroma ingest | `205 + 112 + 103 = 420` chunks in `malloy_subgraphs` |
| **Repo truth** | `verify_index_coverage.py --config workspace/publisher.config.json` → **`3/3 served package(s) have a RAG context`, exit 0** (185 / 108 / 95 measures) |
| Money measures present | same command with `--require jaffle_shop:Total_Revenue --require jaffle_shop:Gross_Margin` → still `3/3`, exit 0 |
| Idempotence (risk-table row) | `index_chroma()` called twice back-to-back: run 1 `count=420`, run 2 `count=420`, contexts identical `[comics, jaffle_shop, thelook_ecommerce]`, sorted-id `sha256` **identical** (`d352313ce6d73302`) — per-context `delete(where=…)` + `upsert` is stable |

Two findings:

1. **The stale `theLook-DEMO__thelook_ecommerce` vectors are immortal.** `index_chroma()` deletes only the `context_id`s it is about to rewrite, so the pre-rename id (205 chunks from the old env prefix) survived the rebuild: the collection held **625 chunks across 4 contexts**, failing this task's literal "exactly 3 context ids". Severity is storage-only — `ChromaRetriever.search_field_items()` queries `where={"$and":[{"context": cid}, {"chunk_type":"field_metric_node"}]}`, so a phantom context can never be returned. Remedy applied locally as a one-off (`collection.delete(where={"context": "theLook-DEMO__thelook_ecommerce"})` → 420 chunks / 3 contexts); **no code change**, because after `TASK-12` untracks `chroma_db` and `.gcloudignore:20` keeps it out of the build context, every CI build starts from an empty directory and cannot inherit an id it did not index. Worth one line in `DEPLOY.md`.
2. **`context/chroma_db/` is now dirty in `git status`** (5 modified binaries + a new `index_metadata.pickle`) — the 9 MB binary diff predicted by `TASK-02` finding 3. It carries no reviewable information and is exactly what `TASK-12` removes from tracking; **do not commit it**.

Working-tree state after this task (RAG repo, all uncommitted): `M` on `run_context_pipeline.py`, `step_1_compile_malloy.js`, `step_3_mcp_dual_pathway_server.py` (Phase 0 + `TASK-01`) and 5 `chroma_db` binaries; `??` on `verify_index_coverage.py`, `scripts/verify_context_coverage.py` (Phase 0) and 9 `context/data/step_*_workspace__*` artifacts; `D` on the 3 `step_*_theLook-DEMO__*` artifacts.

#### `GATE-01` record (2026-10-28) — **PASS, 3/3**

Stage 3 was started exactly as the container starts it, from the rebuilt index, and called over the real HTTP transport (`POST /mcp` → `tools/call malloy_getContext`), not by importing the module:

```bash
cd context && PORT=8099 UPSTREAM_MCP=http://127.0.0.1:9/mcp \
  /tmp/ragvenv/bin/uvicorn step_3_mcp_server.step_3_mcp_dual_pathway_server:app --port 8099
```

`UPSTREAM_MCP` was pointed at a dead port on purpose: if the server had fallen back to relaying, the call would have errored instead of answering. `/healthz` came back `{"status":"ok","contexts_preloaded":3,"contexts_expected":3,"contexts_indexed":3,"missing":[]}`.

| Package | Query | Sections | Section-1 fields | Verdict |
|---|---|---|---|---|
| `jaffle_shop` | *"total revenue and gross margin by customer city"* | 3/3 | **95** | **PASS** |
| `comics` | *"how many comics are there and how many have news stories"* | 3/3 | 108 | **PASS** |
| `thelook_ecommerce` | *"total revenue by product category"* | 3/3 | 185 | **PASS** |

The `jaffle_shop` body opens with `=== 1. CANONICAL EXECUTABLE FIELDS ===` and its first two bullets are `* Total_Revenue (measure): Gross revenue including tax.` and `* Gross_Margin (measure): Gross margin after supply cost, including tax.`; Section 3 emits

```
run: cafe_explore -> {
  group_by: cafe_customers.Lifetime_spend
  aggregate:
    Total_Revenue
    Gross_Margin
    …
}
```

which is the exact `run:` block `TASK-01` executed against MotherDuck (`7226.67 / 5820.95`). The 14-field bridge is gone: all three packages returned their full field set (`FULL_SCHEMA_MAX_FIELDS=500` ⇒ `full_mode`), 95/108/185 fields against a bridge that carried 14 fields and no measures.

Harness: `/tmp/g01_gate.py` (asserts 3 section headers, >14 Section-1 fields, measures present in both Section 1 and the Section-3 template). Reproduce:

```bash
/tmp/ragvenv/bin/python /tmp/g01_gate.py http://127.0.0.1:8099   # exit 0 = PASS
```

One retrieval-quality observation, **out of scope for this gate but worth a backlog line:** for *"by customer city"* the Section-3 grain came back as `cafe_customers.Lifetime_spend` rather than a city dimension — `resolve_entity_dimension()` picks the entity's first canonical dimension, so grain selection is entity-driven, not phrase-driven. It does not affect measure coverage (the bug this document exists for) and touches no file in the change budget.

#### `TASK-04` record (2026-10-28) — **DONE** (command-level; container half of `GATE-02` env-blocked)

`Dockerfile:34-61` now replaces the `--fresh` + narrow-config `RUN`:

```dockerfile
ARG MOTHERDUCK_TOKEN
ENV PYTHONPATH="/app/context:/app/context/shared"
RUN python3 /app/context/orchestration/verify_index_coverage.py --soft \
      --config /app/workspace/publisher.config.json \
 && MOTHERDUCK_TOKEN="${MOTHERDUCK_TOKEN}" \
    python3 /app/context/orchestration/run_context_pipeline.py --all --index-chroma \
      --config /app/workspace/publisher.config.json \
 && python3 /app/context/orchestration/verify_index_coverage.py \
      --config /app/workspace/publisher.config.json
```

Three deltas from the plan text, each forced by a measurement:

1. **`ARG MOTHERDUCK_TOKEN` is new and required.** The plan assumed a token-less `docker build` would quietly produce a `thelook_ecommerce`-only image. It does not: the pipeline hard-exits on the first failed compile (measured — exit 1, 11 errors, *graphs already present*). Passed as `ARG`, not `ENV`, so the token is in no layer; `TASK-08` must therefore pass it through a `cloudbuild.yaml` (`buildArgs` + `availableSecrets`), because `gcloud builds submit --tag` has no way to carry build args.
2. **A hard `verify_index_coverage.py` was appended after the pipeline.** The plan's single `--soft` line only *reports* the incoming coverage; the appended hard check makes an incomplete image unbuildable, which is the actual "fail loudly" requirement. `--soft` stayed in front so the log always shows the incoming state before the rebuild.
3. **Nothing was added for the `chroma_db` present/absent split** — it turned out to need no code: `chromadb.PersistentClient(path=...)` creates the directory when absent, and the per-context `delete(where={"context": …})` + `upsert` from `TASK-03` makes a pre-existing copy safe. Both shapes were verified rather than assumed.

Verification (Docker is unavailable in this environment, so the `RUN` line was executed verbatim in image-shaped trees — `cp -a` of the repo root, `PYTHONPATH`/cwd set as the image sets them, `python3` = `/tmp/ragvenv/bin/python3` = same pinned dependency set):

| # | Build context | Steps 1/2/3 exit | Coverage after | Chunks |
|---|---|---|---|---|
| 1 | `chroma_db` **absent**, graphs present, token (Cloud Build path) | `0 / 0 / 0` | 3/3 | 420 |
| 2 | `chroma_db` **present**, graphs present, token (local build path) | `0 / 0 / 0` | 3/3 | 420 |
| 3 | graphs present, **no token** | `0 / 1 / —` | — (build fails) | 420 untouched |
| 4 | clean clone: no graphs, no `chroma_db`, token | `0 / 0 / 0` | 0/3 → **3/3** | 420 |
| 5 | **nothing under `context/data/` at all** (a plain `git clone` — the graphs and domain contexts are untracked) + token | `0 / 0 / 0` | 0/3 → **3/3** | 420 |

Case 5 exists because cases 1-4 still had the untracked `step_1_*_domain_context.json` files on disk: the curated domain contexts for all three packages are `??` in git, so a CI checkout starts with an empty `context/data/`. Result: identical graphs anyway — 205/112/103 chunks and 185/108/95 measures, i.e. the full clone reproduces the local index exactly. The verifier even warns up front (`⚠️ workspace__jaffle_shop: domain context missing (Path A routing quality degraded)`), then `extract_context` derives them. Checked the consequence instead of assuming it: the derived files are **byte-identical** to the curated ones (`identical_json=True`, 47/27/88 `keyword_mappings`, same `fallback_explore` for `cafe_explore`/`comics_explore`/`ecommerce_explore`), so the warning is precautionary here and CI loses no routing quality. No task needed — but if anyone hand-edits a domain context, it must be committed or the edit silently loses to derivation in CI.

Case 1 and 2 both ended with `contexts {thelook 205, comics 112, jaffle_shop 103}` in Chroma — the existing index is re-indexed in place, not duplicated, which is the idempotence proven in `TASK-03` holding under the real build sequence. Case 4 is the "plain `docker build` with a token" path and shows the `--soft` line doing its job: it printed `0/3 served package(s) have a RAG context` with the exact fix command, exited 0, and the pipeline then built all three.

Case 3 is the one that changed the plan: `--soft` reported `3/3` (the graphs were right there), and the pipeline still failed, because validation recompiles sources rather than trusting artifacts. That is correct behaviour — it is also why the token cannot be treated as optional anywhere in the build path.

Emulation harness: `/tmp/g02_emulate.sh` (cases 1-3, prints the post-run Chroma state) and `/tmp/g02_case4.txt` (case 4). Reuse a run:

```bash
bash /tmp/g02_emulate.sh                              # cases 1-3, ~7 min (2 x 1.1 GB copies)
cd /tmp/g02/ci && rm -rf context/chroma_db context/data/step_1_*_raw_extracted.json \
    context/data/step_2_*.json                        # then rerun step 1-3 for case 4
rm -rf context/data/*                                 # case 5: a git clone has no data/ at all
```

**Not verified here:** `COPY`/`ENTRYPOINT`/`EXPOSE` assembly, i.e. the container half of `GATE-02` — no Docker daemon on this machine (see the `GATE-02` note). So `TASK-04`'s acceptance is met at the level of "the build step does the right thing in every build-context shape"; "the image serves `contexts_indexed == contexts_expected`" is proven for the tree, not yet for a container.

#### `TASK-05` record (2026-10-28) — **DONE**

One decorator pair on the existing handler (`step_3_mcp_dual_pathway_server.py:872-891`), no logic change:

```python
@app.get("/context/healthz")   # monitored path — GFE does not reserve /context/*
@app.get("/healthz")           # alias for 127.0.0.1, docker run, Cloud Run probes
async def health_check():
```

Measured against a locally served instance (`PORT=8099`, `UPSTREAM_MCP` pointing at a dead port so any proxying is visible as a failure):

| Request | Result | Meaning |
|---|---|---|
| `GET /context/healthz` | `200` · `{"status":"ok",…,"contexts_expected":3,"contexts_indexed":3,"indexed":[…3…],"missing":[]}` | the §6 fix: the same payload is now reachable on a path Google Frontend does not intercept |
| `GET /healthz` | `200` | alias intact for local runs and the `docker run` half of `GATE-02` |
| `GET /health` | `502` | still proxied to the Node Publisher actuator (dead upstream ⇒ 502, so it is not app-owned) |
| `openapi.json` paths | `/`, `/context/healthz`, `/healthz`, `/mcp`, `/{full_path}` | the two health routes are registered ahead of the catch-all, so they cannot be swallowed by it |

`GATE-01` was re-run after the edit as a regression check: still **PASS (3/3)**, 95/108/185 Section-1 fields — the health routes did not disturb `/mcp` interception (which is matched on `method == "tools/call"` + tool name, not on path).

### Phase 2 — make the image keep what CI builds

| ID | Task | Files | Acceptance | Effort | Status |
|---|---|---|---|---|---|
| `TASK-04` | Replace the `--fresh` + narrow-config `RUN` line with the idempotent build | `Dockerfile` | Image builds; within the image `verify_index_coverage.py` reports the same coverage the build context had; `--fresh` gone. Must tolerate `context/chroma_db/` being **present** (local build) or **absent** (Cloud Build, `.gcloudignore:20`) — see `TASK-02` record finding 3 | 15 m | **`DONE`** — command-level proven in 5 build-context shapes; container half of `GATE-02` blocked (no Docker daemon in this env) |
| `TASK-05` | Move the health route: `/context/healthz` + alias, keep it before the catch-all | `context/step_3_mcp_server/step_3_mcp_dual_pathway_server.py` | `GET /context/healthz` returns the coverage JSON; `/health` still returns the Node actuator; `/healthz` alias still works on `127.0.0.1` | 15 m | **`DONE`** — `/context/healthz` 200 + coverage JSON, `/healthz` 200 alias, `/health` still proxied (502 with a dead Node upstream) |

**`GATE-02` — image fidelity:** `docker build` + `docker run` locally → `curl /context/healthz` shows `contexts_expected == contexts_indexed`.

> **Status after `TASK-04`:** the *command* half is proven (5 build-context shapes, `TASK-04` record); the *container* half could not run here — this machine has no Docker daemon (`/var/run/docker.sock` absent, `docker info` → `Failed to initialize: protocol not available`, `systemctl start docker` needs a password that is not available to the agent). Run exactly this on a machine with Docker before `TASK-12`:
> ```bash
> cd /home/maxantipev/analytics-malloy-publisher-rag
> docker build --build-arg MOTHERDUCK_TOKEN="$MOTHERDUCK_TOKEN" -t publisher:gate02 .
> docker run --rm -p 8099:8080 -e PORT=8080 -e UPSTREAM_MCP=http://127.0.0.1:9/mcp publisher:gate02 &
> sleep 25 && curl -s localhost:8099/healthz   # expects contexts_expected == contexts_indexed == 3
> ```
> The emulation already covers everything the container would test except image assembly itself (`COPY`/`ENTRYPOINT`): same tree, same `PYTHONPATH`, same interpreter dependencies, same three commands, `contexts_indexed == contexts_expected == 3`.

### Phase 3 — automation (both repos)

| ID | Task | Files | Acceptance | Effort | Status |
|---|---|---|---|---|---|
| `TASK-06` | Grant the deploy identity `secretAccessor` on `motherduck-token` (§5.2) | — (one `gcloud` command) | `gcloud secrets versions access` succeeds **as the CI identity** | 5 m | **`DONE`** — binding applied (3 principals, baseline captured); behavioural proof lands with `GATE-03` |
| `TASK-07` | Add `scripts/build_context_index.sh` with the secret preflight, npm ci, non-`--fresh` pipeline, verify | `scripts/build_context_index.sh` (new) | Runs green locally; with the token deliberately unset it fails in < 5 s with an actionable message | 30 m | **`DONE`** — 163 s green (3/3, 420 chunks); 2 s on an unreadable secret |
| `TASK-08` | Wire the index build into the deploy workflow, before `gcloud builds submit`, with `MOTHERDUCK_TOKEN` from Secret Manager (`::add-mask::`); **also supply the token to the image build itself** (`cloudbuild.yaml` with `buildArgs` + `availableSecrets`, replacing `--tag`, because a cloudbuild `--tag` run cannot carry build args — see `TASK-04` record) | `.github/workflows/deploy-publisher.yml`, `cloudbuild.yaml` (new) | A workflow run logs "index coverage 3/3" before the image step, and the image step succeeds with the token passed as a build arg | 35 m | **`DONE`** — 2 steps added + `cloudbuild.yaml` via `secretEnv`; the run itself is `GATE-03` |

**`GATE-03` — CI owns the index:** one real deploy run from `main` produces a revision whose `verify_context_coverage.py` result is `3/3` **without** any local step.

#### `TASK-06` record (2026-10-28) — **DONE** (binding applied; proof of use deferred to `GATE-03`)

Applied exactly the §5.2 command, after capturing the baseline policy so the change is reversible and provable:

```
$ gcloud secrets get-iam-policy motherduck-token --project my-1-st-project-training   # before
roles/secretmanager.secretAccessor →
    669258319971-compute@developer.gserviceaccount.com     (Cloud Run runtime)
    669258319971@cloudbuild.gserviceaccount.com            (Cloud Build)

$ gcloud secrets add-iam-policy-binding motherduck-token \
    --project my-1-st-project-training \
    --member serviceAccount:malloy-analytics-user@my-1-st-project-training.iam.gserviceaccount.com \
    --role roles/secretmanager.secretAccessor
Updated IAM policy for secret [motherduck-token].
```

The policy now holds three principals: the two above **plus** the deploy identity — nothing was removed, and `remove-iam-policy-binding` with the same four arguments reinstates today's state exactly. The IAM condition on `malloy-analytics-user@` is untouched, so the grant is still reachable only from `attribute.repository/antipev/analytics-engineering`.

**What is *not* proven, and why that is acceptable here:** the acceptance in §5.4 says "as the CI identity". Impersonating `malloy-analytics-user@` from this machine needs `roles/iam.serviceAccountTokenCreator`, which this user does not hold, and `gcloud policy-troubleshoot iam` would enable an API it does not currently use. Both were declined rather than papered over: the evidence is the policy document (which is what `secretAccessor` *means*), and the behavioural proof is `GATE-03` — the first real workflow run resolves the token with this identity or fails in the new preflight. A policy grant with no consumer yet cannot be proven any other way without borrowing credentials.

#### `TASK-07` record (2026-10-28) — **DONE**

`scripts/build_context_index.sh` (new, 193 lines) — five numbered sections matching the header comment: token preflight, `npm ci --omit=dev`, interpreter resolution, the pipeline, the coverage assertion.

Three things it does that the plan text did not spell out, each forced by a measurement:

1. **Environment first, Secret Manager second** (`resolve_token`). If `MOTHERDUCK_TOKEN` is already exported it is used as-is, so a developer never needs `gcloud`; otherwise the secret is read with the *caller's* identity, which is what makes the CI path the same code as the local path. On failure it prints the `gcloud secrets add-iam-policy-binding` line with the actual caller address filled in — `tail -1` of the gcloud error is included so a typo'd secret name is not reported as a permissions problem.
2. **The pipeline imports Stage 3 unconditionally** (`run_context_pipeline.py:68`), so `chromadb, fastapi, uvicorn, httpx` must be importable even when only Stages 1-2 will run. Rather than assume the caller's interpreter has them, the script creates `context/.venv-index` and installs `context/orchestration/requirements.txt` into it. `.gitignore` gained `.venv-index/` in the same commit, and `.dockerignore` already covers `context/.venv*`, so the venv cannot leak into the image.
3. **`--require jaffle_shop:Total_Revenue --require jaffle_shop:Gross_Margin` by default.** Coverage alone ("3/3 contexts") would still be satisfiable by three field-only contexts; the two measures are the thing the original bug destroyed, so they are asserted by name and the flags are overridable.

Verification, in the order it was run:

| Step | Command | Result |
|---|---|---|
| syntax | `bash -n scripts/build_context_index.sh` | clean (`shellcheck` not installed here) |
| usage | `./scripts/build_context_index.sh --help` | prints the header block, exit 0 |
| fast fail | `env -u MOTHERDUCK_TOKEN SECRET_NAME=no-such-secret-xyz ./scripts/build_context_index.sh` | **exit 1 in 2 s** — `NOT_FOUND` line + the binding command, no pipeline started |
| full run | `./scripts/build_context_index.sh` | **exit 0 in 163 s** |
| coverage | last lines of that run | `✅ thelook 205/185 · comics 112/108 · jaffle_shop 103/95`, `3/3 served package(s) have a RAG context`, `[index] index coverage 3/3` |
| chunks | `Total chunks indexed in ChromaDB 'malloy_subgraphs': 420` | same 420 as `TASK-03` — the non-`--fresh` path re-indexes in place, it does not duplicate |

Two operational notes from that run: `npm ci` prints ~15 `EBADENGINE` warnings when the ambient `node` is old (`/usr/bin/node` is v12 here) — the compile itself resolved `nvm` v24 and succeeded, so the warnings are noise, but **Node ≥ 20 is a prerequisite** of Stage 1 either way. And the run rewrote the five tracked `chroma_db` binaries with identical logical content (420 chunks, same 205/112/103 split, verified by reading the collection back); those binary diffs were reverted rather than committed, which is `TASK-12`'s argument in miniature.

A second run (`--skip-npm`, token already in the environment — the other branch of the preflight) reproduced the same index: `[OK]` for all three, `205/112/103`, `Total chunks … 420`, `3/3`. So the script is idempotent across both token sources, and the only thing a rebuild changes is the Chroma binary layout.

#### `TASK-08` record (2026-10-28) — **written and parsed; `GATE-03` needs a real run from `main`**

Three files, two in the engineering repo and one in the RAG repo.

**`deploy-publisher.yml` — two new steps ahead of the image step.**

```yaml
- name: Resolve the MotherDuck token
  env: { SECRET_NAME: motherduck-token }
  run: |
    TOKEN=$(gcloud secrets versions access latest --secret="$SECRET_NAME" --project "$PROJECT_ID")
    echo "::add-mask::${TOKEN}"
    echo "MOTHERDUCK_TOKEN=${TOKEN}" >> "$GITHUB_ENV"
- name: Build the RAG context index
  working-directory: publisher
  run: ./scripts/build_context_index.sh --config workspace/publisher.config.json
```

The masking step is a step of its own, not an `env:` block, because `::add-mask::` has to run *before* any line can echo the value; `$GITHUB_ENV` then carries it to the next step without it ever entering `argv` in the clear. Its failure branch repeats the `add-iam-policy-binding` command using `$GCP_SERVICE_ACCOUNT`, so a lost binding reads as an IAM problem in the step summary rather than as a Malloy error later. The image step became `gcloud builds submit --config cloudbuild.yaml --substitutions=_IMAGE="$IMAGE" --quiet .`.

**`cloudbuild.yaml` (new, RAG repo) — the only way to pass a build arg.**

```yaml
- name: 'gcr.io/cloud-builders/docker'
  entrypoint: 'bash'
  args: ['-c', 'docker build --build-arg MOTHERDUCK_TOKEN="$$MOTHERDUCK_TOKEN" -t "${_IMAGE}" .']
availableSecrets:
  secretManager:
    - versionName: projects/$PROJECT_ID/secrets/motherduck-token/versions/latest
      env: MOTHERDUCK_TOKEN
options: { machineType: 'E2_HIGHCPU_8', logging: CLOUD_LOGGING_ONLY }
```

`$` vs `$$` is the subtle part: Cloud Build substitutes `${_IMAGE}` into the step before the shell sees it, so `$$MOTHERDUCK_TOKEN` is *shell* expansion of the `secretEnv` variable and the token appears in no substitution, no log line and no layer. `E2_HIGHCPU_8` because the in-image index build compiles 12 files at ~3.1 s each; `CLOUD_LOGGING_ONLY` so the build needs no GCS log bucket. The config is read from the uploaded source directory, which is `publisher/`, hence `working-directory: publisher` on the step.

**Deliberate duplication, recorded so nobody "optimises" it away.** The workflow index build and the in-image build do the same pipeline run. That is not an oversight: `.gcloudignore:20` excludes `context/chroma_db`, so whatever the workflow builds **cannot reach the image** — its value is *fail-fast*, ~3 minutes earlier, with the coverage table printed in the workflow log where a human reads it, instead of buried in Cloud Build output. It also exercises exactly the permission `TASK-06` granted, with the CI identity, before any build minutes are spent. If deploy latency ever matters more than that, the step to delete is the workflow one — the image build already guarantees coverage via the hard `verify_index_coverage.py` after the pipeline.

Validation performed here (no CI run — that is `GATE-03`, and it deploys):

```
$ python3 -c "import yaml; d=yaml.safe_load(open('.github/workflows/deploy-publisher.yml'))"
workflow OK, steps: 13        # ... 6 Copy packages · 7 Resolve token · 8 Build index · 9 Build image ...
$ python3 -c "import yaml; d=yaml.safe_load(open('cloudbuild.yaml'))"
cloudbuild OK: ['steps', 'images', 'availableSecrets', 'options', 'timeout']
```

`actionlint` is not installed in this environment, so the workflow was checked by YAML parse and step enumeration only; the run in `GATE-03` is the real validator. **Open risk carried into `GATE-03`:** `gcloud builds submit --config` from `working-directory: publisher` uploads `publisher/`, and Cloud Build's own default service account must hold `secretAccessor` for `availableSecrets` — §5.1 shows it does (`669258319971@cloudbuild.gserviceaccount.com`), which is also why adding `TASK-06`'s binding did not and should not change that path.

#### `GATE-03` record (2026-10-28) — **PASS on the third attempt**, after three real bugs

Three dispatched runs, two failures, each one a defect that no amount of local testing had surfaced. This is the gate earning its keep.

**Attempt 1 (`40788177339`) — the checker lied about a measure that was present.**

```
[OK] workspace__thelook_ecommerce / comics / jaffle_shop
✅ Indexed 205 / 112 / 195 chunks … Total chunks: 512
❌ workspace__jaffle_shop  -> missing required measure(s): Total_Revenue, Gross_Margin
```

195 chunks for `jaffle_shop`, against 103 measured locally in `TASK-03`. Cause, found by reproducing the CI tree locally (`scripts/sync_semantic_layer.sh ../analytics-engineering/semantic_layer/workspace workspace/semantic_layer` + the same pipeline): **the canonical package changed shape upstream** in `bd6bd7f fix(jaffle_shop): … drop cafe_explore`. It is now a unified-star bridge — `2_refinements/bridge.malloy`, explore `cafe_bridge_explore`, every measure reached through a joined source — so Stage 2 writes `cafe_orders.Total_Revenue`, and `verify_index_coverage.py` compared whole normalized strings only and therefore called a present measure missing.

Consequences, both recorded rather than smoothed over:

- **`workspace/semantic_layer/` is gitignored and rsync'd from `analytics-engineering` by CI**, so the copy under `publisher/` is a build artifact. The copy used for the `TASK-01`/`GATE-01` measurements was the **pre-bridge** package: those numbers (103 chunks, 95 measures) describe a package that is no longer shipped. Re-measured on the canonical package: 195 chunks, 184 fields, `cafe_orders.Total_Revenue` and `cafe_orders.Gross_Margin` present in Section 1 *and* in the Section-3 template — so the money measures are still served, they are just qualified. The bug this project exists for (two packages with no context at all) is unchanged by the rename.
- Fix (`f3b88055`): `resolve_required()` matches the whole field **or its final segment**, and the report now prints `(Total_Revenue -> cafe_orders.Total_Revenue)` so the qualification stays visible instead of being hidden by a lenient match. Negative case still fails: `--require jaffle_shop:Not_A_Measure` → exit 1. The committed Stage-1/2 artifacts were refreshed to the canonical shape (512 chunks total).

**Attempt 2 (`40789317181`) — the build config was valid YAML and still wrong.**

The index step went green (3/3, 512 chunks), then Cloud Build rejected the image step in 3 seconds:

```
ERROR: (gcloud.builds.submit) INVALID_ARGUMENT: invalid build:
invalid secrets: secretEnv "MOTHERDUCK_TOKEN" is defined without being used
```

`availableSecrets` only *makes a secret available*; the step must also name it in `secretEnv`, which the first draft of `cloudbuild.yaml` did not. Nothing local could catch that: the file parses, and the failure lives in Cloud Build's own validation. Also measured in that run: the upload was `7995 file(s) totalling 643.8 MiB`, because `scripts/build_context_index.sh` had created `context/.venv-index` (513 MB) and neither `.gcloudignore` (`**/.venv/` only) nor `.dockerignore` (`context/.venv/` only) covered the new name — with `COPY context/ ./context/`, the venv would have been baked into the image as well as uploaded. Fix (`0e3d7c07`): `secretEnv: ['MOTHERDUCK_TOKEN']` on the step, and `**/.venv-index/` in both ignore files.

**Attempt 3 (`40790026847`) — green end to end, no local step.**

| Evidence | Value |
|---|---|
| workflow conclusion | `completed success` |
| index step | `3/3 served package(s) have a RAG context` — 205 / 112 / 195 chunks, 512 total |
| Cloud Build | `SUCCESS`, in-image `verify_index_coverage` prints `3/3` (205/185, 112/108, 195/184) |
| revision | `malloy-publisher-mcp-00035-tqq`, 100% of traffic |
| workflow coverage step | `✅ thelook 19507 chars · comics 6857 · jaffle_shop 17665 — 3-section context returned`, `3/3` |
| `GET /context/healthz` (public) | `200` · `contexts_preloaded 3 · contexts_expected 3 · contexts_indexed 3 · missing []` |
| independent harness `/tmp/g03_gate.py <service-url>` | `GATE-03: PASS (3/3)` — 3/3 sections, 184/108/185 Section-1 fields, `Total_Revenue` + `Gross_Margin` in Section 1 and Section 3 for `jaffle_shop` |

Two side notes. The harness had to be pointed at `/context/healthz`: production still answers `/healthz` with Google's 404, which confirms §6 outside any doubt and is the first production use of the `TASK-05` route. And `TASK-06`'s acceptance is now behavioural as well as documentary — the token step resolved the secret as `malloy-analytics-user@` on all three runs, which is exactly the proof that could not be produced locally.

### Phase 4 — enforcement and cleanup

| ID | Task | Files | Acceptance | Effort | Status |
|---|---|---|---|---|---|
| `TASK-09` | Set repository variable `ENFORCE_CONTEXT_COVERAGE=true` | GitHub repo settings | A deliberately broken package makes the deploy fail with the missing-context message | 5 m | **`DONE`** — variable set through `gh api -X POST .../actions/variables` (`gh` in this environment has no `variable` subcommand); run `40799108206` shows `ENFORCE_CONTEXT_COVERAGE: true` in the step env and passes `3/3`; the fatal path is proven in the `GATE-04` record (same command, exit 1 enforced vs exit 0 with `--soft`) |
| `TASK-10` | Add the Cloud Run startup probe on `/context/healthz` | `deploy-publisher.yml` (`gcloud run deploy` flags) | Revision serves traffic only after the probe passes; a crashing Stage 3 keeps the old revision on traffic | 20 m | **`DONE`** (`4fcec73`, fixed in `5b99d70`) — `--startup-probe httpGet.path=/context/healthz,httpGet.port=5050,periodSeconds=5,timeoutSeconds=2,failureThreshold=24` plus an assert step that reads the field back off the service; attempt 1 taught that startup probes reject `successThreshold` |
| `TASK-11` | Add the uptime check + alert (`contexts_indexed < contexts_expected`) | Cloud Monitoring | Alert fires when one context is removed manually | 20 m | **`DONE`** — `scripts/setup_context_monitoring.py` creates an uptime check on `/context/healthz` with a content matcher on `missing: []` plus an alert policy; the alert's `documentation` field needs a `mimeType` or the create call fails |
| `TASK-12` | Delete `publisher.context.config.json`; untrack `context/chroma_db/` | `Dockerfile`, `deploy-publisher.yml`, `run_context_pipeline.py` default, docs, `.gitignore` | No reference to the narrow config remains (`grep -r publisher.context.config`); `git ls-files context/chroma_db` is empty and `.gitignore` covers it (rationale: `TASK-02` record finding 3) | 25 m | **`DONE`** — narrow config deleted, 85 binaries untracked, `.gitignore` covers `context/chroma_db/`; the measurable effect is in the build: source upload went from `7995 file(s) totalling 643.8 MiB` to `133.6 MiB` |
| `TASK-13` | Commit Phase 0 + Changes 1-4 in reviewable commits and update `DEPLOY.md` | both repos | Each commit independently green; docs mention `/context/healthz`, the reserved-path rule, and the token rotation step | 20 m | **`DONE`** — 4 commits across the two repos (`refactor(context)…`, `feat(run)…`, `fix(probe)…`, `fix(deploy)…`, plus `fix(context): refuse to ship a stale domain context`); `DEPLOYMENT.md` documents the reserved path, the probe (and the `successThreshold` trap), token rotation and the domain-context guard |

**`GATE-04` — the real end state:** from a cold browser session, `malloy_getContext` for all three packages returns ≥ 3 sections and the money measures; `Total_Revenue = 7226.67`, `Gross_Margin = 5820.95`, `Order_Count = 686` for `jaffle_shop` match a direct MotherDuck query; and a merge that drops a package from the config fails the deploy.

#### `GATE-04` record (2026-10-29) — **PASS**, and it caught one more real defect

Three dispatched runs, one of them red for a reason that no local check could see, and one
production defect found by reading the deployment the way a client would.

**Attempt 1 (`40793774219`) — the probe flag was rejected wholesale.**

```
ERROR: (gcloud) Key [successThreshold] not recognized for startup probe.
```

`successThreshold` exists on liveness and readiness probes only; startup probes succeed once by
definition. gcloud rejects the *entire* `--startup-probe` value, so the revision was never even
created — the failure was 3 s into the deploy step, after a full image build. Fixed in
`5b99d70` (workflow) and `2a14ae7e` (RAG docs, one paragraph so nobody re-adds it).
`gcloud run deploy --help` in this environment does not list probe flags at all, which is why
only an executed run could surface it — the same lesson as `GATE-03`: the gate is the test.

**Attempt 2 (`40795703724`) — green, and the armed gate runs inside it.** New revision
`malloy-publisher-mcp-00036-wt4`, 100% of traffic. The facts this run had to produce:

| evidence | value |
|---|---|
| index step | `✅ Indexed 205 / 112 / 195 chunks`, `3/3 served package(s) have a RAG context` |
| probe read-back (`Assert the revision probes /context/healthz`) | `startup probe: path=/context/healthz port=5050` |
| traffic | `Revision malloy-publisher-mcp-00036-wt4 is serving 100% of traffic.` |
| coverage step env | `ENFORCE_CONTEXT_COVERAGE: true` — no `--soft` is appended |
| coverage step result | `✅ thelook 19507 · comics 6857 · jaffle_shop 17665 chars — 3/3 served package(s) return a real RAG context` |
| `GET /context/healthz` (public) | `200` · `contexts_preloaded 3 · contexts_indexed 3 · missing []` |
| `gcloud run services describe` | `startupProbe.httpGet.path=/context/healthz`, `periodSeconds=5`, `failureThreshold=24` |
| cold-session harness `/tmp/g03_gate.py` | `GATE-01: PASS (3/3)` — 184/108/185 Section-1 fields, `Total_Revenue` + `Gross_Margin` + `Order_Count` in Section 1 *and* Section 3 |
| direct MotherDuck query (`duckdb`, `data_warehouse_demo.marts.cafe_orders`) | `[(686, 7226.67, 5820.95)]` — `Order_Count`, `Total_Revenue`, `Gross_Margin`, exactly the numbers this gate names |

**The armed gate is a gate, not a label.** The same command, same service, one flag apart:

```
$ verify_context_coverage.py --base-url <prod> --require jaffle_shop:Not_A_Measure
❌  workspace/jaffle_shop  17628 chars  executableContext lacks: Not_A_Measure
2/3 served package(s) return a real RAG context.        exit=1     ← what CI runs now
$ ... --soft
2/3 served package(s) return a real RAG context.        exit=0     ← what CI ran before TASK-09
```

**The defect `GATE-04` found: a stale domain context was answering discovery.** Asking the
live service to list the sources of `jaffle_shop` returned an explore that does not exist:

```
"name": "cafe_explore", "modelPath": "3_explores/cafe_explore.malloy"
→ malloy_executeQuery with that path: Resource not found
workspace/jaffle_shop/3_explores/cafe_explore.malloy
```

The canonical package had renamed its explore to `cafe_bridge_explore`, and
`context/data/step_1_*_domain_context.json` — derived once, then curated, and therefore never
regenerated — still described `cafe_explore`. Stage 2 copied that name into its intent prose and
the discovery tier served it verbatim. This is the same class of failure the project exists to
remove: *an artifact that answers confidently about a model it no longer matches*. Two changes,
committed as `dd3ec228`:

1. **Stage 1 refuses to ship it.** If the stored `fallback_explore` or `published_file` is not
   among the explores this run just compiled, the pipeline exits 1 and prints the `--fresh`
   command to run. Verified both ways: the stale file stops the build (`exit=1`), and the CI index
   step passes once the file is regenerated (`3/3`, 515 chunks).
2. **The artifact is regenerated.** `run_context_pipeline.py --context workspace__jaffle_shop
   --fresh`, domain JSON plus Step-2 graph recommitted. Only `jaffle_shop` was stale; `comics` and
   `thelook_ecommerce` already matched. Section 3 had always been right — the router resolves the
   explore from the graph — which is why `GATE-01`/`GATE-03` never saw this: they ask questions,
   and only the *listing* tier hands back the stored name.

**Attempt 3 (`40799108206`) — green with the fix, and the fix is visible from outside.** Revision
`malloy-publisher-mcp-00037-ct6`, 100% of traffic, probe asserted, index `198 chunks` for
`jaffle_shop`, coverage `3/3` under enforcement. The discovery tier now answers:

| package | advertised source | modelPath |
|---|---|---|
| `jaffle_shop` | `cafe_bridge_explore` | `3_explores/cafe_bridge_explore.malloy` |
| `comics` | `comics_explore` | `3_explores/comics_explore.malloy` |
| `thelook_ecommerce` | `ecommerce_explore` | `3_explores/ecommerce_explore.malloy` |

**Open finding carried out of `GATE-04` (`OPEN-1`).** The *advertised* `modelPath` is still not
accepted by the relayed `malloy_executeQuery`: every package answers
`Resource not found: workspace/<pkg>/<modelPath>`, whether the path is package-relative,
environment-relative or absolute, on all three packages. So `malloy_getContext` grounds an agent
correctly and the measures are proven present and numerically correct against MotherDuck, but an
agent that copies `modelPath` into `malloy_executeQuery` gets an error — the Publisher resolves
model paths against a different root than the package `location` in
`workspace/publisher.config.json`. It is a Publisher integration question, not a coverage one, and
it does not change what this gate measures; it is recorded here rather than smoothed over, with
the reproduction above, because it is the next thing a client will hit.


### Dependency graph

```
TASK-01 → TASK-02 → TASK-03 → GATE-01 ─┬→ TASK-04 → GATE-02
                                        └→ TASK-05
TASK-06 → TASK-07 → TASK-08 → GATE-03 → TASK-09 → TASK-10 → TASK-11
                                                        ↘ TASK-12 → TASK-13 → GATE-04
```

`TASK-04`/`TASK-05` can run in parallel with `TASK-06`…`TASK-08` (different files, no shared state). `TASK-12` must come **after** `GATE-03`, otherwise the image loses its only working fallback while CI still depends on the narrow config.


---

## 8. Progress tracker

Update these boxes as work lands; they are the single place where progress is read from.

```
PHASE 0  Observability (applied, uncommitted)                    ██████████ 100%
  [x] verify_index_coverage.py            (new, validated: 0/3 → exit 1)
  [x] verify_context_coverage.py          (new, validated: 1/3 → exit 1)
  [x] run_context_pipeline.py             (per-context Chroma delete)
  [x] step_3_mcp_dual_pathway_server.py   (boot + relay warnings, healthz payload)
  [x] deploy-publisher.yml                (11th step, warn-only)

PHASE 1  Compilable packages                                     ██████████ 100%
  [x] TASK-01  motherduck connection in step_1 compiler  (DONE — both pkgs compile, thelook hash unchanged)
  [x] TASK-02  local compile proof (DONE — 12/12 .malloy OK with token, 12/12 fail without)
  [x] TASK-03  local index 3/3 without --fresh  (DONE — 420 chunks / 3 contexts, verify_index_coverage 3/3)
  [x] GATE-01  local malloy_getContext returns 3 Section-Summary  (PASS — 95/108/185 fields, Total_Revenue in S1+S3)

PHASE 2  Image fidelity                                          ██████████ 100%
  [x] TASK-04  Dockerfile idempotent build (no --fresh)  (DONE — 5 build-context shapes, hard post-verify)
  [x] TASK-05  /context/healthz + /healthz alias  (DONE — 200 + coverage JSON; /health still proxied)
  [~] GATE-02  docker run → contexts_indexed == contexts_expected  (command-level PASS; no Docker daemon here)

PHASE 3  Automation                                             ██████████ 100%
  [x] TASK-06  IAM: secretAccessor for the deploy identity  (DONE — binding applied, 3 principals; use proven in GATE-03)
  [x] TASK-07  scripts/build_context_index.sh + preflight  (DONE — 163 s, 3/3, 420 chunks; 2 s fast-fail)
  [x] TASK-08  workflow step with masked token  (DONE — 2 steps + cloudbuild.yaml; CI run is GATE-03)
  [x] GATE-03  real deploy run → 3/3 with no local step  (PASS on attempt 3 — rev 00035-tqq; 3 bugs found and fixed)

PHASE 4  Enforcement and cleanup                                 ██████████ 100%
  [x] TASK-09  ENFORCE_CONTEXT_COVERAGE=true  (DONE — run 40799108206 shows the flag and passes 3/3 enforced)
  [x] TASK-10  Cloud Run startup probe  (DONE — startupProbe.path=/context/healthz read back from the service)
  [x] TASK-11  uptime check + alert  (DONE — setup_context_monitoring.py; probe on /context/healthz + alert policy)
  [x] TASK-12  delete publisher.context.config.json + untrack chroma_db  (DONE — upload 643.8 → 133.6 MiB)
  [x] TASK-13  commits + DEPLOY.md  (DONE — 5 commits across both repos; doc covers probe, reserved path, rotation, guard)
  [x] GATE-04  cold-session proof for all three packages  (PASS on attempt 3 — rev 00037-ct6; found + fixed the stale domain context; OPEN-1 recorded)
```

### Iteration rules

1. **One task, one commit.** `TASK-02`, `TASK-03` and `TASK-07` are verification steps and produce no commit of their own — they gate the commit before them.
2. **A gate that fails reopens the phase, it does not open the next one.** `GATE-01` failing means `TASK-01` was wrong, not that Phase 2 should start.
3. **Never arm enforcement before `GATE-03`.** `ENFORCE_CONTEXT_COVERAGE=true` on a repository whose CI does not build the index turns every unrelated deploy red.
4. **Re-measure with the same two commands after every phase** — `verify_index_coverage.py --config workspace/publisher.config.json` (repo truth) and `scripts/verify_context_coverage.py --base-url …` (deployed truth). A phase is only finished when both agree.

---

## 9. Risks, and how each is contained

| Risk | Likelihood | Containment |
|---|---|---|
| MotherDuck compile is slower than the build budget (3 packages instead of 1) | low — **measured in `TASK-02`: ≈3.1 s per `.malloy` file (12 files ⇒ 37.5 s), Stage 1 ≈2.5-4 s per package** | the pipeline is per-package and `npm ci` is cached; projected ≈55 s for 3 packages, far under the ~4 min threshold, so the Docker-side build stays viable |
| Token leaks into logs | low | `::add-mask::` in the workflow; the token is read into `$GITHUB_ENV`, never echoed; Malloy errors print a redacted DSN |
| `TASK-12` removes the fallback too early | medium | hard ordering: `TASK-12` after `GATE-03` |
| Startup probe stalls a healthy boot | low | `failureThreshold=24` at 5 s = 2 min budget, longer than today's 60 s Node wait |
| Image size grows (3 graphs instead of 1) | low | graphs are JSON in the hundreds of KB; `context/chroma_db` stays out of the upload via `.gcloudignore` |
| `delete(where={"context": …})` changes semantics on a Chroma version bump | low — **closed by `TASK-03`: two consecutive `index_chroma()` runs gave `count=420`, 3 contexts, identical sorted-id `sha256 d352313ce6d73302`** | the assertion lives in `TASK-03`'s record; re-run `/tmp/t03_idempotence.py` after any `chromadb` bump |
| A stale context id survives re-indexing and pads the collection | low — observed in `TASK-03` (`theLook-DEMO__…`, 205 chunks) | cannot leak: Path B filters `context == cid`; one-off `collection.delete(where={"context": …})`; structurally impossible in CI once `TASK-12` untracks `chroma_db` |
| A **curated domain context** outlives the package it describes | **observed in `GATE-04`** — `jaffle_shop` still advertised `cafe_explore` after the rename to `cafe_bridge_explore` | closed by `dd3ec228`: Stage 1 compares `fallback_explore`/`published_file` with the explore it just compiled and exits 1 with the `--fresh` command; regenerated and recommitted |
| The discovery tier's `modelPath` is rejected by `malloy_executeQuery` | **observed in `GATE-04`; open (`OPEN-1`)** — all three packages answer `Resource not found: workspace/<pkg>/<modelPath>` | recorded with a reproduction, not fixed: `malloy_getContext` grounding and the measures are unaffected; the Publisher resolves model paths against a different root than the package `location` |

| The image build now needs `MOTHERDUCK_TOKEN`, and `gcloud builds submit --tag` cannot pass build args | **high — measured in `TASK-04`** (no token ⇒ exit 1 even with graphs present, because Stage 1 recompiles) | token goes in as `ARG`/`--build-arg` (never `ENV`, so it is in no layer); `TASK-08` must convert the image step to a `cloudbuild.yaml` with `buildArgs` + `availableSecrets` — now part of `TASK-08`'s acceptance, not optional polish |
| Someone reads the `--soft` verify as "the build cannot fail" | low | the `RUN` line ends with a **hard** `verify_index_coverage.py`; `--soft` only reports the incoming state before the rebuild (`TASK-04` record) |

**Rollback:** every change is a single file. `git revert` of `TASK-01`/`TASK-04` restores today's behaviour exactly — `TASK-01` is a no-op without `MOTHERDUCK_TOKEN`, and `TASK-04` reverts to the narrow-config `RUN` (which needs no token, at the cost of the `jaffle_shop`/`comics` regression). The service can be pinned to `malloy-publisher-mcp-00034-n7p` while reverting.


---

## 10. Appendix — reproduce every number in this document

```bash
# repo truth (3/3 as of TASK-03)
cd ~/analytics-malloy-publisher-rag
python3 context/orchestration/verify_index_coverage.py --config workspace/publisher.config.json
python3 context/orchestration/verify_index_coverage.py --json --soft | python3 -m json.tool
# money measures must survive: expect exit 0
python3 context/orchestration/verify_index_coverage.py --config workspace/publisher.config.json \
  --require jaffle_shop:Total_Revenue --require jaffle_shop:Gross_Margin

# rebuild the graphs + index exactly as the image does it (needs the Stage-3 deps;
# --fresh must NOT be passed, or the curated domain contexts are regenerated)
python3 -m venv /tmp/ragvenv && /tmp/ragvenv/bin/pip install -r context/orchestration/requirements.txt
MOTHERDUCK_TOKEN=… /tmp/ragvenv/bin/python context/orchestration/run_context_pipeline.py --all --index-chroma

# exactly 3 context ids in the collection (a 4th means a stale pre-rename id survived)
/tmp/ragvenv/bin/python -c "import chromadb,collections; c=chromadb.PersistentClient(path='context/chroma_db').get_or_create_collection('malloy_subgraphs'); d=c.get(include=['metadatas']); print(c.count(), collections.Counter(m['context'] for m in d['metadatas']))"

# packages the pipeline can actually see
python3 context/orchestration/run_context_pipeline.py --list

# deployed truth (1/3 today, expected 3/3 after GATE-03)
python3 scripts/verify_context_coverage.py \
  --base-url https://malloy-publisher-mcp-bolcwt6srq-nn.a.run.app \
  --config workspace/publisher.config.json

# the exact blocker A evidence
gcloud secrets get-iam-policy motherduck-token --project my-1-st-project-training \
  --format='value(bindings[].role, bindings[].members)'
gcloud iam service-accounts get-iam-policy malloy-analytics-user@my-1-st-project-training.iam.gserviceaccount.com \
  --format='value(bindings[].role, bindings[].members)'
gcloud run services describe malloy-publisher-mcp --region northamerica-northeast1 \
  --format='value(spec.template.spec.serviceAccountName, status.latestReadyRevisionName)'

# the exact blocker B evidence
for p in /healthz /healthz/ /healthz2 /health /context/healthz; do
  printf '%-18s %s\n' "$p" "$(curl -sS -o /dev/null -w '%{http_code}' "https://malloy-publisher-mcp-bolcwt6srq-nn.a.run.app$p")"
done
curl -s -o /dev/null -w '%{http_code}\n' https://analytics-dagster-bolcwt6srq-nn.a.run.app/healthz   # control: also 404

# the numbers the fix must reproduce
# Total_Revenue = 7226.67   Gross_Margin = 5820.95   Order_Count = 686

# --- TASK-01 proof (compile + measure values) -------------------------------
# token locally: your own user can read the secret, which is exactly why CI's
# malloy-analytics-user@ cannot (blocker A / TASK-06)
gcloud secrets versions access latest --secret=motherduck-token \
  --project my-1-st-project-training > /tmp/.md_token   # 436 bytes, chmod 600
export MOTHERDUCK_TOKEN="$(tr -d '\r\n' < /tmp/.md_token)"

node --check context/step_1_extract/step_1_compile_malloy.js

# must still fail identically without the token (unknown connection)
env -u MOTHERDUCK_TOKEN node context/step_1_extract/step_1_compile_malloy.js \
  workspace/semantic_layer/jaffle_shop/3_explores/cafe_explore.malloy

# must succeed with it: 95 fields / 33 measures for jaffle, 108 / 8 for comics
node context/step_1_extract/step_1_compile_malloy.js \
  workspace/semantic_layer/jaffle_shop/3_explores/cafe_explore.malloy > /tmp/j.json
node context/step_1_extract/step_1_compile_malloy.js \
  workspace/semantic_layer/comics/3_explores/comics_explore.malloy > /tmp/c.json

# thelook_ecommerce must be byte-identical to HEAD (no motherduck reference)
git show HEAD:context/step_1_extract/step_1_compile_malloy.js \
  > context/step_1_extract/tmp_orig_compile.js
node context/step_1_extract/tmp_orig_compile.js \
  workspace/thelook_ecommerce/3_explores/ecommerce_explore.malloy > /tmp/t.orig
node context/step_1_extract/step_1_compile_malloy.js \
  workspace/thelook_ecommerce/3_explores/ecommerce_explore.malloy > /tmp/t.new
sha256sum /tmp/t.orig /tmp/t.new        # both c946c8de…, 65 788 bytes
rm context/step_1_extract/tmp_orig_compile.js

# --- TASK-02 proof (real Stage-1 entry point + whole-package validation) -----
python3 context/step_1_extract/step_1_python_context_retrieval_script.py \
  --context workspace__jaffle_shop       # exit 0, 4.0 s, 33 measures, 4 intents
python3 context/step_1_extract/step_1_python_context_retrieval_script.py \
  --context workspace__comics            # exit 0, 2.5 s,  8 measures, 2 intents

# whole-package compile = what run_context_pipeline.py:243 checks first
# (calls step1.validate_package for every package; 12 .malloy files ⇒ 37.5 s)
# with token  -> OK workspace__comics (4 files) / OK workspace__jaffle_shop (8 files)
# without     -> 12/12 files fail  (env -u MOTHERDUCK_TOKEN)

# the pipeline itself needs the service deps even for a Stage-1/2-only run,
# because run_one_package imports Stage 3 unconditionally (line 68):
python3 -m venv /tmp/ragvenv
/tmp/ragvenv/bin/pip install -q -r context/orchestration/requirements.txt
/tmp/ragvenv/bin/python context/orchestration/run_context_pipeline.py --list
```

