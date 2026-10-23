# jaffle_shop — model layer

The e-commerce data product, modelled as a **Unified Star Schema**: six tables, one bridge, and `_key_cafe_*` surrogate keys that exist only to join them.
Three layers, one direction: `staging` → `intermediate` → `marts`.

| Layer | Models | Materialisation | What they do |
| :--- | :--- | :--- | :--- |
| staging | `stg_cafe_customers`, `stg_cafe_locations`, `stg_cafe_orders`, `stg_cafe_order_items`, `stg_cafe_products`, `stg_cafe_supplies` | view | Read `source('ecom', 'raw_*')` — schema `ingest_jaffle_shop`, the tables `jaffle_shop_ingestion_job` writes — and clean them. |
| intermediate | `int_cafe_*` | view | The **key layer**: staging grain and staging columns, plus the `_key_cafe_*` each table contributes to the USS. |
| intermediate | `int_cafe_bridge` | view | The USS bridge, one row per record per reporting table, identified by `stage`. |
| marts | `cafe_customers`, `cafe_locations`, `cafe_orders`, `cafe_order_items`, `cafe_products`, `cafe_supplies` | table | The reporting tables the semantic layer reads. |
| marts | `cafe_bridge` | table | Materialised copy of `int_cafe_bridge`, so the bridge is scanned from `marts`, not recomputed per query. |

## Conventions

- **`_key_cafe_*` columns are the only join keys.** Each mart selects its own key and the keys of the tables it relates to (`cafe_order_items` carries five), so any two marts can be joined through the bridge without a composite predicate. The semantic-layer packages select these columns by name — renaming one breaks the Publisher build, not just dbt.
- **`cafe_bridge` repeats the definition on purpose.** The bridge view is defined once in `intermediate/int_cafe_bridge.sql`; the mart is a materialised copy of the same SQL. Changing one without the other is a bug.
- **Tests live in `_*.yml` next to the models.** `_cafe_models.yml` holds the uniqueness and `relationships` tests plus the `dbt_utils.expression_is_true` arithmetic checks (`lifetime_spend_pretax + lifetime_tax_paid = lifetime_spend`, `order_total = subtotal + tax_paid`); `_stg_cafe_models.yml` and `_sources.yml` describe the staging layer and the sources.

## What CI does with a change here

`transformation_dbt/**` is a deploy path: a pull request runs `dbt deps` and `dbt parse` in the `validate` job of `Deploy Dagster`, and a merge to `main` builds a new image and deploys it. The models are not built by CI — `jaffle_shop_transformation_job` builds them on demand — so a change that parses but is semantically wrong reaches BigQuery the next time that job runs, not on merge (§12 item 5 of the CI runbook).
