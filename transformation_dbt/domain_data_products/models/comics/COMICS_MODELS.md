# comics — model layer

XKCD data, from the raw table to the two marts the semantic layer reads.
Three layers, one direction: `staging` → `intermediate` → `marts`.

| Layer | Model | Materialisation | What it does |
| :--- | :--- | :--- | :--- |
| staging | `stg_comics` | view | Reads `source('xkcd_duckdb', 'raw_comics_v2')` — schema `ingest_xkcd`, the table `comics_ingestion_job` writes — and deduplicates with `QUALIFY ROW_NUMBER() OVER (PARTITION BY num) = 1`, so the newest row per comic number wins. |
| intermediate | `int_comics` | view | Derives the fields the mart needs: `_key_comics`, `publication_date` from `year`/`month`/`day`, `is_valid_date`, `tooltip_text`, `img_url`, and the `nr_*` text metrics. |
| marts | `comics` | incremental | Appends to `marts.comics` keyed on `_key_comics` (`unique_key`), one row per comic, joined to `_key_calendar`. |
| marts | `calendar` | table | Date dimension, `2006-01-01` to today, one row per day. Includes the current-period anchors and YoY equivalents the comics lookups need. |

## Conventions

- **`_key_*` columns are join keys.** `_key_comics` is the comic number as a surrogate key; `_key_calendar` is the publication date, and `comics._key_calendar` is tested against `calendar._key_calendar` with a `relationships` test. Do not rename these: the semantic-layer packages select them by name.
- **Nothing is hard-coded to a project or dataset.** Schema names come from `dbt_project.yml`, so the same models build into whatever target the profile points at.
- **Tests live in `_*.yml` next to the models.** `_comics.yml` carries `not_null` + `unique` on `_key_comics`, the calendar relationship, and `accepted_values` on the derived date-validity column; `_calendar.yml` carries `not_null` + `unique` on `_key_calendar`.

## What CI does with a change here

`transformation_dbt/**` is a deploy path: a pull request runs `dbt deps` and `dbt parse` in the `validate` job of `Deploy Dagster`, and a merge to `main` builds a new image and deploys it. Nothing runs the models themselves — the monthly `comics_transformation_job` is the only thing that builds them, so a change that parses but is semantically wrong reaches BigQuery on the next scheduled run, not on merge (§12 item 5 of the CI runbook).
