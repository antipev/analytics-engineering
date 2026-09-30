# Imports the core Dagster framework.
import dagster as dg

# Imports the Pandas library for tabular data structures.
import pandas as pd

# Imports the requests library for making HTTP API calls.
import requests

# Imports DuckDB for loading data into the database.
import duckdb

# Imports JSON for parsing our schema configuration files.
import json

# Imports Python's built-in thread pool. We use it to download many XKCD
# pages at the same time instead of one after another, which makes the
# whole backfill finish many times faster.
from concurrent.futures import ThreadPoolExecutor

# Imports MotherDuck Credentials
from dotenv import load_dotenv


#----------------------------------------------------------------------
# Load environment variables from .env file
load_dotenv()
#----------------------------------------------------------------------


# ---------------------------------------------------------------------
# Function 1: Handle DuckDB connection and setup
# ---------------------------------------------------------------------
def get_duckdb_connection(
    #db_path: str = "src/xkcd_dagster/defs/data/xkcd.duckdb", # Local DuckDB
    db_path: str = "md:xkcd", # Mother Duck
):
  """Connects to the DuckDB database file and returns the connection object."""
  con = duckdb.connect(db_path)
  return con


# ---------------------------------------------------------------------
# Function 2: Fetch a specific comic by number or fallback to latest
# ---------------------------------------------------------------------
def fetch_xkcd_comic(comic_number: int = None) -> dict:
    """Fetches comic metadata dynamically by ID, or gets the latest if none provided."""
    if comic_number is not None:
        url = f"https://xkcd.com/{comic_number}/info.0.json"
    else:
        url = "https://xkcd.com/info.0.json"
        
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    # Assign to variable instead of returning immediately
    data = response.json()
    
    # Force extra_parts to always be a JSON string or None
    if "extra_parts" in data and isinstance(data["extra_parts"], dict):
        data["extra_parts"] = json.dumps(data["extra_parts"])
    elif "extra_parts" not in data or data["extra_parts"] is None:
        data["extra_parts"] = None
    else:
        data["extra_parts"] = str(data["extra_parts"])
    
    # Return transformed data
    return data


# ---------------------------------------------------------------------
# Function 3: Validate schema and insert into versioned DuckDB table
# ---------------------------------------------------------------------
def insert_comic_to_duckdb(con, df: pd.DataFrame, schema_version: str, target_schema: str) -> None:
    """Validates incoming DataFrame schema against a JSON config, and 
    automatically builds the target table name using the base name + version.
    """
    # Dynamically construct the configuration file path based on the version parameter
    config_path = f"src/xkcd_dagster/defs/data/schema_config_{schema_version}.json"
    
    # 1. Load the expected schema configuration
    with open(config_path, "r") as f:
        config = json.load(f)
    
    base_table_name = config["table_name"] 
    expected_columns = config["columns"] 
    
    # 2. Automatically combine the table name and version (Prefix the schema explicitly so DuckDB doesn't default to 'main')
    table_name_only = f"{base_table_name}_{schema_version}"
    target_table = f"{target_schema}.{table_name_only}"

    # 3. Ensure the target schema exists before writing
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {target_schema};")

    # 4. Fill any missing schema columns with None automatically
    for col in expected_columns.keys():
        if col not in df.columns:
            df[col] = None
    
    # Force extra_parts column to string/object so DuckDB creates a VARCHAR column
    if "extra_parts" in df.columns:
        df["extra_parts"] = df["extra_parts"].astype("string")

    # 5. Re-order DataFrame columns to match the JSON configuration order exactly
    df = df[list(expected_columns.keys())]

    # 6. Check for missing or extra columns
    actual_columns = set(df.columns)
    expected_cols_set = set(expected_columns.keys())
    
    if actual_columns != expected_cols_set:
        raise ValueError(
            f"SCHEMA BREAK: Column mismatch detected for '{target_table}'!\n"
            f"Expected: {sorted(expected_cols_set)}\n"
            f"Received: {sorted(actual_columns)}"
        )
        
    # 7. Check for data type changes
    for col, expected_type in expected_columns.items():
        actual_type = str(df[col].dtype)
        if actual_type != expected_type:
            raise ValueError(
                f"SCHEMA BREAK: Data type changed for column '{col}' in '{target_table}'!\n"
                f"Expected type: {expected_type}\n"
                f"Received type: {actual_type}"
            )

    # 8. Create the versioned table dynamically if it doesn't exist, then insert
    con.register("df", df)
    con.execute(f"CREATE TABLE IF NOT EXISTS {target_table} AS SELECT * FROM df WHERE 1=0")
    cols = ", ".join(expected_columns.keys())
    con.execute(f"INSERT INTO {target_table} ({cols}) SELECT {cols} FROM df")


# ---------------------------------------------------------------------
# Dagster Asset: Orchestrates Incremental Ingestion & Gap Filling
# ---------------------------------------------------------------------
@dg.asset(key="raw_comics_v2", group_name="comics", kinds={"python"})
# - `key="raw_comics_v2"` → the asset's __unique ID__. Without it, the key is the function name (`step_1_ingestion_comics`).
# Setting it to `raw_comics_v2` makes it __match__ the dbt source you declared in `_sources.yml` (`asset_key: ["raw_comics_v2"]`). 
# When the two keys match, Dagster draws the edge: `raw_comics_v2` (ingestion) → `stg_comics` → `int_comics` → `comics`.
# - `group_name="comics"` → puts the asset into the __"comics" group__ in the UI (so it sits next to the comics dbt models, not the default group).

def step_1_ingestion_comics(context: dg.AssetExecutionContext) -> dg.MaterializeResult:
    """Backfill any missing XKCD comics into DuckDB.

    We fetch many comics over HTTP at the same time (in parallel) instead of
    one after another. That matters because each request only takes ~0.2-0.3
    seconds, but there are ~3,300 of them: doing them one-by-one meant ~16
    minutes of mostly waiting. Overlapping the requests cuts that to ~1-2 min.
    """
    active_schema_version = "v2"
    target_schema = "ingest"
    target_table = f"{target_schema}.raw_comics_{active_schema_version}"

    # 1. Open a connection to DuckDB (our local database file).
    con = get_duckdb_connection()

    # Make sure the schema we will write into exists. "IF NOT EXISTS" makes
    # this safe to run every time.
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {target_schema};")

    # 2. Read every comic number we already have stored, so we only download
    #    the gaps. We keep the numbers in a Python set, which answers
    #    "is this number missing?" very quickly.
    try:
        existing_ids = con.execute(f"SELECT num FROM {target_table}").fetchall()
        existing_set = {row[0] for row in existing_ids}
    except Exception:
        # If the table does not exist yet, there is nothing stored, so the
        # set of comics we already have is just empty.
        existing_set = set()

    # 3. Ask the XKCD API for the newest comic, so we know how high to count.
    latest_api_comic = fetch_xkcd_comic(comic_number=None)
    max_api_id = latest_api_comic["num"]

    # 4. Build the list of comic numbers we still need to fetch.
    #    Note: we skip #404 on purpose, because xkcd.com/404 has no comic
    #    (it is the site's "not found" page).
    missing_ids = [
        i for i in range(1, max_api_id + 1)
        if i != 404 and i not in existing_set
    ]

    context.log.info(f"Comics in DuckDB: {len(existing_set)}. Missing to fetch: {len(missing_ids)}.")

    # If nothing is missing, we are already up to date, so stop here.
    if not missing_ids:
        context.log.info("Database is fully up to date! No missing comics to fetch.")
        con.close()
        return dg.MaterializeResult()

    # 5. Download the missing comics in parallel, then write them in batches.
    #
    #    A "batch" is just a list of comic dictionaries we collect in memory
    #    and hand to DuckDB in ONE insert. Batching means far fewer trips to
    #    the database (500 rows at a time instead of 1 at a time).
    #
    #    "max_workers" is how many downloads run at the same time. 20 is a
    #    good balance: fast, but still polite to the XKCD server.
    success_count = 0    # how many comics we have successfully stored
    batch = []           # comics collected but not yet written to DuckDB
    batch_size = 500     # write to DuckDB once the batch reaches this size

    def _fetch(i: int):
        """Download ONE comic. Return the error instead of raising it.

        Returning the error (rather than raising) means one broken comic does
        not stop the whole run; we check for errors back on the main thread.
        We also must NOT call context.log here, because this function runs on
        a background thread and Dagster's logging is not thread-safe.
        """
        try:
            return fetch_xkcd_comic(comic_number=i)
        except Exception as e:
            return e

    # ThreadPoolExecutor runs several _fetch() calls at the same time across
    # separate threads. pool.map() returns results in the SAME order as the
    # numbers we gave it, so comics still go into DuckDB in ascending order.
    with ThreadPoolExecutor(max_workers=20) as pool:
        for i, result in zip(missing_ids, pool.map(_fetch, missing_ids)):
            # If the download failed, _fetch returned the exception -> log it
            # and move on to the next comic.
            if isinstance(result, Exception):
                context.log.warning(f"Could not fetch comic #{i}: {result}")
                continue

            batch.append(result)

            # When the batch is full, write it to DuckDB and start a new one.
            if len(batch) >= batch_size:
                df = pd.DataFrame(batch)
                insert_comic_to_duckdb(con, df, schema_version=active_schema_version, target_schema=target_schema)
                success_count += len(batch)
                batch = []
                context.log.info(f"Progress: Successfully ingested {success_count} comics so far (Current ID: #{i})...")

    # Write whatever is left over (the last, smaller-than-500 batch, if any).
    if batch:
        df = pd.DataFrame(batch)
        insert_comic_to_duckdb(con, df, schema_version=active_schema_version, target_schema=target_schema)
        success_count += len(batch)

    # Close the database connection and report how many comics we stored.
    con.close()
    context.log.info(
        f"Successfully backfilled/fetched {success_count} missing comic(s) "
        f"using schema version: {active_schema_version}."
    )

    return dg.MaterializeResult()
