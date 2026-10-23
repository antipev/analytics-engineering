# models — two data products, one convention

Two independent data products share this dbt project. They never reference each other's models; they only share the conventions below.

| Directory | Source schema | Marts | Read by |
| :--- | :--- | :--- | :--- |
| `comics/` | `ingest_xkcd` (`source('xkcd_duckdb', …)`) | `comics`, `calendar` | the `comics` semantic-layer packages |
| `jaffle_shop/` | `ingest_jaffle_shop` (`source('ecom', …)`) | `cafe_*`, `cafe_bridge` | the `jaffle_shop` semantic-layer packages |

## The three layers

1. **`staging/`** — one model per source table, materialised as a **view**, schema `staging`. Rename, cast, deduplicate; no joins, no business logic.
2. **`intermediate/`** — views, schema `intermediate`. Joins, derived columns, and the `_key_*` surrogate keys. `int_cafe_bridge` defines the Unified Star Schema bridge.
3. **`marts/`** — `table` or `incremental`, schema `marts`. What the semantic layer and any dashboard read. Nothing in this layer references another mart.

## Rules that CI will not catch for you

- **`_key_*` names are an interface, not a detail.** The semantic-layer packages select `_key_comics`, `_key_calendar` and `_key_cafe_*` by name. Renaming one parses cleanly and then breaks the Publisher build, because dbt parse does not know who reads the table.
- **`dbt parse` is all the pull request checks.** Schemas, refs, Jinja and `dbt deps` — not a single row is read. A model that compiles but is semantically wrong ships with the deploy and is discovered the next time the job runs (§12 item 5 of the CI runbook).
- **Tests live next to the models**, in `_*.yml`. They run in the monthly jobs, not in CI: `comics_transformation_job` and `jaffle_shop_transformation_job`.
- **Documentation in `README.md` files is inert.** dbt only reads `{% docs %}` blocks; a README here documents the layout for humans and changes no model.
