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


# ---------------------------------------------------------------------
# Function 1: Handle DuckDB connection and setup
# ---------------------------------------------------------------------
def get_duckdb_connection(
    db_path: str = "src/xkcd_dagster/defs/data/xkcd.duckdb",
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
        
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------
# Function 3: Validate schema and insert into versioned DuckDB table
# ---------------------------------------------------------------------
def insert_comic_to_duckdb(con, df: pd.DataFrame, schema_version: str) -> None:
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
    
    # 2. Automatically combine the table name and version
    target_table = f"{base_table_name}_{schema_version}"

    # Fill any missing schema columns with None automatically
    for col in expected_columns.keys():
        if col not in df.columns:
            df[col] = None

    # 3. Check for missing or extra columns
    actual_columns = set(df.columns)
    expected_cols_set = set(expected_columns.keys())
    
    if actual_columns != expected_cols_set:
        raise ValueError(
            f"SCHEMA BREAK: Column mismatch detected for '{target_table}'!\n"
            f"Expected: {sorted(expected_cols_set)}\n"
            f"Received: {sorted(actual_columns)}"
        )
        
    # 4. Check for data type changes
    for col, expected_type in expected_columns.items():
        actual_type = str(df[col].dtype)
        if actual_type != expected_type:
            raise ValueError(
                f"SCHEMA BREAK: Data type changed for column '{col}' in '{target_table}'!\n"
                f"Expected type: {expected_type}\n"
                f"Received type: {actual_type}"
            )

    # 5. Create the versioned table dynamically if it doesn't exist, then safely append
    con.execute(f"CREATE TABLE IF NOT EXISTS {target_table} AS SELECT * FROM df WHERE 1=0")
    con.append(target_table, df)


# ---------------------------------------------------------------------
# Dagster Asset: Orchestrates Incremental Ingestion & Gap Filling
# ---------------------------------------------------------------------
@dg.asset
def step_1_ingestion(context: dg.AssetExecutionContext) -> dg.MaterializeResult:
    active_schema_version = "v2"
    target_table = f"raw_comics_{active_schema_version}"

    # 1. Connect to DuckDB using Function 1
    con = get_duckdb_connection()

    # 2. Get all existing comic numbers currently in DuckDB (to detect holes/gaps)
    try:
        existing_ids = con.execute(f"SELECT num FROM {target_table}").fetchall()
        existing_set = {row[0] for row in existing_ids}
    except Exception:
        # If table doesn't exist yet, start with an empty set
        existing_set = set()

    # 3. Get the latest comic ID available on the XKCD API
    latest_api_comic = fetch_xkcd_comic(comic_number=None)
    max_api_id = latest_api_comic["num"]

    # 4. Find any missing IDs from 1 up to the latest API comic (skipping #404)
    missing_ids = [
        i for i in range(1, max_api_id + 1) 
        if i != 404 and i not in existing_set
    ]

    context.log.info(f"Comics in DuckDB: {len(existing_set)}. Missing to fetch: {len(missing_ids)}.")

    # If no missing comics, we are fully up to date!
    if not missing_ids:
        context.log.info("Database is fully up to date! No missing comics to fetch.")
        con.close()
        return dg.MaterializeResult()

    # 5. Fetch and insert missing comics comic-by-comic
    success_count = 0
    for i in missing_ids:
        try:
            new_comics = [fetch_xkcd_comic(comic_number=i)]
            df = pd.DataFrame(new_comics)
            insert_comic_to_duckdb(con, df, schema_version=active_schema_version)
            success_count += 1

            # PROGRESS LOG
            if success_count % 50 == 0:
                context.log.info(f"Progress: Successfully ingested {success_count} comics so far (Current ID: #{i})...")

        except Exception as e:
            context.log.warning(f"Could not fetch comic #{i}: {e}")

    # Close connection after loop finishes
    con.close()
    context.log.info(
        f"Successfully backfilled/fetched {success_count} missing comic(s) "
        f"using schema version: {active_schema_version}."
    )

    return dg.MaterializeResult()