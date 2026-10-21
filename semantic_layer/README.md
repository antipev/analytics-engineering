# Malloy semantic layer

This directory is the source of truth for the Malloy packages served by both
Credible and the self-hosted Malloy Publisher.

## Layout

```text
semantic_layer/
├── README.md
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
        │   ├── customers.malloy
        │   ├── locations.malloy
        │   ├── order_items.malloy
        │   ├── orders.malloy
        │   ├── products.malloy
        │   └── supplies.malloy
        └── 3_explores/
            └── cafe_explore.malloy
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
> source (`comics_explore` and `cafe_explore`), and both return rows through
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

The MotherDuck token belongs in the repository-root `.env` as
`MOTHERDUCK_TOKEN`. Never commit the token or a populated Publisher config.

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
query `comics_explore` and `cafe_explore` to verify MotherDuck connectivity.
Stop the server with `Ctrl+C`.

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
