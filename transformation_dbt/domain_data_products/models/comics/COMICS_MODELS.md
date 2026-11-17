# comics — model layer

XKCD data, from the raw table to the two marts the semantic layer reads.
Three layers, one direction: `staging` → `intermediate` → `marts`.

| Layer | Model | Materialisation | What it does |
| :--- | :--- | :--- | :--- |
| staging | `stg_comics` | view | Reads `source('xkcd_duckdb', 'raw_comics_v2')` — schema `ingest_xkcd`, the table `comics_ingestion_job` writes — and deduplicates with `QUALIFY ROW_NUMBER() OVER (PARTITION BY num) = 1`, so the newest row per comic number wins. |
| intermediate | `int_comics` | view | Derives the fields the mart needs: `_key_comics`, `publication_date` from `year`/`month`/`day`, `is_valid_date`, `tooltip_text`, `img_url`, and the `nr_*` text metrics. |
| marts | `comics` | incremental | Appends to `marts.comics` keyed on `_key_comics` (`unique_key`), one row per comic, joined to `_key_calendar`. |
| marts | `calendar` | table | Date dimension, `2006-01-01` to today, one row per day. Includes the current-period anchors and YoY equivalents the comics lookups need. |
| staging | `stg_comics_categories` | table, **manual** | Off by default; a one-time DeepSeek-generated category list (6–10 rows). Not part of any scheduled run — see the section below. |

## Conventions

- **`_key_*` columns are join keys.** `_key_comics` is the comic number as a surrogate key; `_key_calendar` is the publication date, and `comics._key_calendar` is tested against `calendar._key_calendar` with a `relationships` test. Do not rename these: the semantic-layer packages select them by name.
- **Nothing is hard-coded to a project or dataset.** Schema names come from `dbt_project.yml`, so the same models build into whatever target the profile points at.
- **Tests live in `_*.yml` next to the models.** `_comics.yml` carries `not_null` + `unique` on `_key_comics`, the calendar relationship, and `accepted_values` on the derived date-validity column; `_calendar.yml` carries `not_null` + `unique` on `_key_calendar`.

## Manual model: `stg_comics_categories` (on demand)

A one-time taxonomy helper, not part of the scheduled build. It is **disabled by default**
(`DBT_DISCOVER_COMIC_CATEGORIES` must be `true`), tagged `manual_ai`, materialises to
`staging.stg_comics_categories`, and produces 6–10 rows of `category_id` / `category_name` /
`definition`. It suggests **the category list only** — it does not classify individual comics,
create embeddings, or write to `comics` / `mart_comics`.

### Input it reads

It uses three columns from `stg_comics` together:

- `title` — comic title
- `alt` — tooltip text, called `tooltip_text` in the mart
- `transcript` — comic dialogue and descriptions, when available

`num` and `year` provide context. Each comic is sent as text:

```text
Comic ID: <num>; year: <year>; part: <n>
Title: ...
Tooltip: ...
Transcript: ...
```

Long comics are split at 12,000 characters (`part` 1, 2, …) so no text is dropped, and the
resulting items are packed into requests of at most 24,000 characters. Every per-batch answer is
reduced hierarchically (“Merge these proposed taxonomies; remove overlap”) before the final list
is produced.

### Does the Python code use Pydantic to guarantee LLM output?

Yes. The model declares the expected shape:

```python
class Category(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    definition: str = Field(min_length=1, max_length=300)

class CategoryList(BaseModel):
    categories: list[Category] = Field(min_length=6, max_length=10)
```

and calls DeepSeek with:

```python
.with_structured_output(CategoryList, method="json_mode")
```

Pydantic checks that the response contains 6–10 categories, each with a valid `name` and
`definition`. Additional code checks for duplicate category IDs and for exactly one
`Other / unclear` row.

It guarantees **validation, not correct reasoning.** Invalid output stops the run instead of being
saved; valid output can still contain poor categories, so the list must be reviewed by a human
before anything downstream relies on it.

### How to run it

```bash
cd transformation_dbt/domain_data_products
set -a && source ../../.env && set +a          # provides DEEPSEEK_API_KEY
export DBT_DISCOVER_COMIC_CATEGORIES=true
dbt run --target motherduck_dev --profiles-dir . --select stg_comics_categories
dbt test --target motherduck_dev --profiles-dir . --select stg_comics_categories
unset DBT_DISCOVER_COMIC_CATEGORIES
```

The offline checks live in `scripts/test_comic_category_discovery.py` (`python
scripts/test_comic_category_discovery.py`, no key, no network). The full plan and review gate are
kept in the local-only, gitignored `DOCUMENTATION/2_Plan_and_Implementation/13_PROJECT_1_Comics_Classification.md`.

## What CI does with a change here

`transformation_dbt/**` is a deploy path: a pull request runs `dbt deps` and `dbt parse` in the `validate` job of `Deploy Dagster`, and a merge to `main` builds a new image and deploys it. Nothing runs the models themselves — the monthly `comics_transformation_job` is the only thing that builds them, so a change that parses but is semantically wrong reaches BigQuery on the next scheduled run, not on merge (§12 item 5 of the CI runbook).
