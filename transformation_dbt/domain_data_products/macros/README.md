# macros — what each one does, and what depends on it

Five macros, three of them load-bearing for the models, two inherited from the starter project.

| Macro | Used by | What it does |
| :--- | :--- | :--- |
| `generate_schema_name` | every model | Overrides dbt's default. dbt normally prefixes a custom schema with the target schema (`transformation_dbt_staging`); this macro returns the custom schema **verbatim**, which is why the warehouse schemas are exactly `staging`, `intermediate` and `marts`, and why `marts.comics` is the name the semantic layer and the ingestion jobs expect. |
| `calendar_macro(start_date, end_date)` | `comics/marts/calendar.sql` only | Builds the date dimension from dbt_utils `date_spine`, then adds the current-period anchors and YoY equivalents. The only argument call in the project: `date '2006-01-01'` to `current_date()`. |
| `cents_to_dollars(column_name)` | `jaffle_shop/staging/stg_cafe_orders.sql`, `stg_cafe_supplies.sql` | Dispatched cast: `default__cents_to_dollars` divides by 100 into `numeric(16,2)`; `spark__cents_to_dollars` rounds instead. BigQuery and DuckDB both take the default. |
| `materialization_raw_sql` (BigQuery) | nothing | Custom materialisation that runs the model's statement as-is, with hooks and no DDL wrapper. Defined for a raw-ingestion path that no model currently selects: `materialized = 'raw_sql'` appears in no model in this project. Kept, not wired up. |
| `materialization_raw_sql` (DuckDB) | nothing | The same materialisation for the DuckDB target, so a `raw_sql` model would parse under `--target duckdb_dev` too. |

## Editing notes

- `generate_schema_name` is why no model needs `+schema:` in `dbt_project.yml`. Changing it renames every relation in the warehouse on the next `dbt run` — the old relations are not dropped, they are orphaned.
- The two `materialization_raw_*` files declare the **same** materialisation name for **different** adapters. Both are needed: `dbt parse` resolves the name per adapter, and a project targeting DuckDB in CI with only the BigQuery file would fail to resolve `raw_sql`.
- `materialization_raw_bq.sql.sql` really does carry a doubled extension. Harmless (dbt reads any `.sql`), but do not "fix" it without re-running `dbt parse` — the path is in the project and in the Dagster `DbtProjectComponent` state under `ingestion/`.
