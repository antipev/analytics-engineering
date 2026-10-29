# Malloy semantic layer

This directory is the source of truth for the Malloy packages served by both
Credible and the self-hosted Malloy Publisher.

## Layout

```text
semantic_layer/
├── MALLOY_SEMANTIC_LAYER.md        # this file
├── publisher.config.json           # local Publisher only
└── workspace/
    ├── comics/
    │   ├── publisher.json          # Credible package manifest
    │   ├── 1_raw_views/
    │   │   └── config.malloy       # MotherDuck table mappings
    │   ├── 2_refinements/
    │   │   ├── comics.malloy
    │   │   └── calendar.malloy
    │   └── 3_explores/
    │       └── comics_explore.malloy
    └── jaffle_shop/
        ├── publisher.json          # Credible package manifest
        ├── 1_raw_views/
        │   └── config.malloy       # MotherDuck table mappings
        ├── 2_refinements/
        │   ├── bridge.malloy
        │   ├── customers.malloy
        │   ├── locations.malloy
        │   ├── order_items.malloy
        │   ├── orders.malloy
        │   ├── products.malloy
        │   └── supplies.malloy
        └── 3_explores/
            └── cafe_bridge_explore.malloy
```

The layered layout follows the same pattern as the reference Publisher
workspace:

1. `1_raw_views/config.malloy` maps physical MotherDuck tables to raw sources.
2. `2_refinements/*.malloy` adds keys, renames, dimensions, measures, and joins.
3. `3_explores/*.malloy` exposes the package-level query surface. The
   `explores` array in `publisher.json` is the explicit allowlist of published
   explores.

> **Publisher deprecation note (2026-10-21):** Publisher logs
> `"explores" in publisher.json is deprecated` when it loads these packages.
> The current behavior is preserved: each package still exposes exactly one
> source (`comics_explore` and `cafe_bridge_explore`), and both return rows through
> Publisher and Credible. The supported replacement is an `index.malloy` file at
> the package root, but the migration is deliberately **not** part of TASK-09 or
> GATE-10. It changes the published package surface and must be validated in both
> serving paths before adoption. See TASK-09a in
> `DOCUMENTATION/2_Plan_and_Implementation/7_PROJECT_1_Credible_GitHub_Implementation.md`
> for the follow-up decision. Until then, keep `explores` and treat the warning
> as expected.

Each package directory is the publishable unit. It must contain `publisher.json`;
`semantic_layer/publisher.config.json` is only a local Publisher configuration
and is never uploaded to Credible.

## Connections

There are two deliberately separate configurations:

| File | Consumer | Purpose |
|---|---|---|
| `../malloy-config.json` | VS Code Malloy extension / Malloy tooling | Defines the `motherduck` connection used by the `.malloy` sources. |
| `publisher.config.json` | Local and deployed Malloy Publisher | Defines the `analytics` environment and its packages. |

The repository-root `malloy-config.json` uses the DuckDB connection type with a
MotherDuck database path and reads the token from `MOTHERDUCK_TOKEN`:

```json
{
  "connections": {
    "motherduck": {
      "is": "duckdb",
      "databasePath": "md:data_warehouse_demo",
      "motherDuckToken": { "env": "MOTHERDUCK_TOKEN" },
      "workingDirectory": "semantic_layer/workspace"
    }
  }
}
```

`publisher.config.json` uses Publisher's dedicated MotherDuck connection type.
Both configurations refer to the same `data_warehouse_demo` database and the
same `motherduck` connection name used by the Malloy source definitions.

## MotherDuck dependency

The sources read from MotherDuck database `data_warehouse_demo`, schema `marts`.
The following tables must exist before Publisher can load or query the packages:

- `marts.calendar`
- `marts.comics`
- `marts.cafe_customers`
- `marts.cafe_locations`
- `marts.cafe_order_items`
- `marts.cafe_orders`
- `marts.cafe_products`
- `marts.cafe_supplies`
- `marts.cafe_bridge`

The packages read the `marts` schema **only**: no `intermediate` and no `staging`
dependency. Every `marts.cafe_*` table now publishes its own `_key_cafe_*` columns as
its **last** columns (defined once in `intermediate/int_cafe_*`), and
`marts.cafe_bridge` exposes the six keys side by side. Each refinement therefore
declares `primary_key: _key_cafe_<table>`, and `cafe_bridge_explore` maps a bridge key
to the mart's own id — `_Key_cafe_orders = cafe_orders.Order_id`, … ,
`_Key_cafe_supplies = cafe_supplies.Supply_uuid` — so there is no helper view, no
synthetic `_Key_cafe_*` dimension on the refinements, and no `intermediate` object.

The MotherDuck token belongs in the repository-root `.env` as
`MOTHERDUCK_TOKEN`. Never commit the token or a populated Publisher config.

### VS Code Malloy extension and `.env`

`.env` is only read by scripts that source it (`set -a; source ../.env; set +a`).
Neither the Malloy CLI nor the VS Code extension loads `.env`; they resolve
`{ "env": "MOTHERDUCK_TOKEN" }` from the **process environment** at connection
time, and when the variable is missing the field is silently omitted. The
connection then attempts `md:data_warehouse_demo` without a token and fails with:

```
Invalid Input Error: ... "Cannot connect to MotherDuck server: no token provided"
```

**Fix for WSL Remote (and any Remote-SSH setup):** put the export in the VS Code
Server environment hook. It is sourced before the server starts, so the Malloy
extension host inherits `MOTHERDUCK_TOKEN` no matter how the editor was
launched, and `malloy-config.json` stays the only (secret-free) Malloy config:

```sh
# ~/.vscode-server/server-env-setup   (chmod 700)
REPO_ENV_FILE=/path/to/analytics-engineering/.env
if [ -f "$REPO_ENV_FILE" ]; then
    MOTHERDUCK_TOKEN=$(
        sed -n 's/^MOTHERDUCK_TOKEN=//p' "$REPO_ENV_FILE" |
            head -n 1 | tr -d '\r' | sed 's/^"//; s/"$//'
    )
    [ -n "$MOTHERDUCK_TOKEN" ] && export MOTHERDUCK_TOKEN
fi
unset REPO_ENV_FILE
```

Restart the server (`Remote: Kill VS Code Server on Host`, or `wsl --shutdown`
from Windows) — a window reload is not enough, the server process is reused.
Verify with:

```bash
pgrep -f 'bootstrap-fork --type=extensionHost' | while read -r p; do
  tr '\0' '\n' < "/proc/$p/environ" | grep -c '^MOTHERDUCK_TOKEN='
done   # 1
```

`export MOTHERDUCK_TOKEN=...` in `~/.bashrc` does **not** work: the WSL server is
started by `wsl.exe`, not by an interactive shell. See
`DOCUMENTATION/2_Plan_and_Implementation/9_PROJECT_1_Malloy WSL.md` for the full
root-cause analysis.

Notebook cells (`.malloynb`) need one more local setting, because the extension cannot map a `vscode-notebook-cell:` URI back to the repository config: set `"malloy.globalConfigDirectory": "~/analytics-engineering"` in `.vscode/settings.json` (git-ignored). It is used only as a fallback, so `.malloy` files keep discovering the tracked `malloy-config.json`. See `DOCUMENTATION/2_Plan_and_Implementation/12_PROJECT_1_Malloy_Notebooks_WSL.md`.

A `malloy-config-local.json` with the literal token also works (Malloy merges it
over the tracked file), but it duplicates the secret in a second file; the
server hook keeps `.env` as the single source of truth.

## Local Publisher

From this directory:

```bash
set -a
source ../.env
set +a

npx --yes @malloy-publisher/server@0.0.244 \
  --server_root . \
  --config ./publisher.config.json \
  --port 4000 \
  --init
```

Open `http://localhost:4000`, confirm both packages load without errors, and
query `comics_explore` and `cafe_bridge_explore` to verify
MotherDuck connectivity. Stop the server with `Ctrl+C`.

## Credible publishing

Credible packages are published from `main` by the GitHub Actions workflow using
`cred publish`. The publishable package roots are
`semantic_layer/workspace/comics` and `semantic_layer/workspace/jaffle_shop`.
The workflow bumps the package patch version for every changed package because
published versions are immutable. Do not publish manually from a laptop once
CI/CD owns the package; a manual publish consumes the version and forces the
next automated publish to use a higher one.

A package is owned by either CI/CD or git-backed modeling, never both. Do not
enroll a package in git-backed modeling while the workflow publishes it.

## No cross-repository symlinks

Do not symlink packages from another repository. Docker build contexts and the
deployed Cloud Run image contain only the Publisher repository, so a symlink to
a sibling checkout is outside the context and will be missing or dangling.
Keep the canonical package files in this repository and copy or mirror them into
the Publisher deployment.
