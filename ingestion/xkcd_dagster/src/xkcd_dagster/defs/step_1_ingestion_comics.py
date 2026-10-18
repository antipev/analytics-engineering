
# Imports the core Dagster framework.
import dagster as dg

# Imports the Pandas library for tabular data structures.
import pandas as pd

# Imports boto3 (AWS S3 SDK). Cloudflare R2 speaks the S3 API, so we use it to read the raw comic files.
import boto3

# Imports DuckDB for loading data into the database.
import duckdb

# Imports JSON for parsing our schema configuration files and raw comic files.
import json

# Imports OS to read credentials from environment variables.
import os

# Imports Python's built-in thread pool. We use it to read many comic files at the same time.
from concurrent.futures import ThreadPoolExecutor

# Imports environment loader for MotherDuck and R2 credentials.
from dotenv import load_dotenv


#----------------------------------------------------------------------
# Load environment variables from .env file
load_dotenv()
#----------------------------------------------------------------------

# Cloudflare R2 bucket and "folder" written by step_0_ingestion_comics.
R2_BUCKET = "xkcd-ingest"
R2_PREFIX = "raw_comics"


# ---------------------------------------------------------------------
# Function 1: Handle R2 connection and setup
# ---------------------------------------------------------------------
def get_r2_client():
  """Creates an S3 client connected to Cloudflare R2 and returns it.

  Needs these values in .env:
    R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY
  """
  account_id = os.environ["R2_ACCOUNT_ID"]
  return boto3.client(
      "s3",
      endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
      aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
      aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
      region_name="auto",
  )


# ---------------------------------------------------------------------
# Function 2: Handle DuckDB connection and setup
# ---------------------------------------------------------------------
def get_duckdb_connection(
    #db_path: str = "src/xkcd_dagster/defs/data/xkcd.duckdb", # Local DuckDB
    db_path: str = "md:xkcd", # Mother Duck
):
  """Connects to the DuckDB database file and returns the connection object."""
  con = duckdb.connect(db_path)
  return con


# ---------------------------------------------------------------------
# Function 3: Read ONE raw comic file from R2
# ---------------------------------------------------------------------
def read_comic_from_r2(s3, comic_number: int) -> dict:
    """Reads raw_comics/<num>.json from R2 and returns it as a dictionary."""
    obj = s3.get_object(Bucket=R2_BUCKET, Key=f"{R2_PREFIX}/{comic_number}.json")
    return json.loads(obj["Body"].read().decode("utf-8"))


# ---------------------------------------------------------------------
# Function 4: Validate schema and insert into versioned DuckDB table
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
# Dagster Config: options you can change in the Dagster UI before a run
# ---------------------------------------------------------------------
class RefreshConfig(dg.Config):
    # Set True in the Dagster UI to drop the MotherDuck table and rebuild it
    # from every file in R2.
    full_refresh: bool = False


# ---------------------------------------------------------------------
# Dagster Asset: Loads raw comic files from R2 into MotherDuck
# ---------------------------------------------------------------------
@dg.asset(
    key="raw_comics_v2",
    group_name="comics",
    kinds={"python"},
    # Runs after step_0 (asset key "raw_comics") finishes, so new files in R2 are loaded in the same run.
    deps=[dg.AssetKey("raw_comics")],
)
# - `key="raw_comics_v2"` → the asset's __unique ID__. Matches the dbt source declared in `_sources.yml` (`asset_key: ["raw_comics_v2"]`).
# When the two keys match, Dagster draws the edge: `raw_comics_v2` (ingestion) → `stg_comics` → `int_comics` → `comics`.
# - `group_name="comics"` → puts the asset into the __"comics" group__ in the UI.

def step_1_ingestion_comics(context: dg.AssetExecutionContext, config: RefreshConfig) -> dg.MaterializeResult:
    """Load every raw comic file in R2 into MotherDuck that is not there yet.

    Step 0 only writes files to R2. This step reads them, applies the schema
    config, and inserts them into MotherDuck.
    """
    active_schema_version = "v2"
    target_schema = "ingest"
    target_table = f"{target_schema}.raw_comics_{active_schema_version}"

    # 1. Open connections to R2 and MotherDuck.
    s3 = get_r2_client()
    con = get_duckdb_connection()

    # Make sure the schema we will write into exists. "IF NOT EXISTS" makes
    # this safe to run every time.
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {target_schema};")

    # 2. Read the comic numbers already in MotherDuck, so we only load the gaps.
    #    Full refresh drops the table first, so everything gets reloaded.
    if config.full_refresh:
        con.execute(f"DROP TABLE IF EXISTS {target_table};")
        existing_set = set()
    else:
        try:
            existing_ids = con.execute(f"SELECT num FROM {target_table}").fetchall()
            existing_set = {row[0] for row in existing_ids}
        except Exception:
            # If the table does not exist yet, nothing is stored.
            existing_set = set()

    # 3. List the comic files that step 0 wrote to R2.
    r2_set = set()
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=R2_BUCKET, Prefix=f"{R2_PREFIX}/"):
        for obj in page.get("Contents", []):
            file_name = obj["Key"].split("/")[-1]
            if file_name.endswith(".json"):
                stem = file_name[:-len(".json")]
                if stem.isdigit():
                    r2_set.add(int(stem))

    # 4. Work out which R2 files are not in MotherDuck yet.
    missing_ids = sorted(r2_set - existing_set)

    context.log.info(f"Comics in MotherDuck: {len(existing_set)}. Files in R2: {len(r2_set)}. To load: {len(missing_ids)}.")

    if not missing_ids:
        context.log.info("MotherDuck is fully up to date with R2. Nothing to load.")
        con.close()
        return dg.MaterializeResult()

    # 5. Read the files in parallel, then insert them in batches.
    success_count = 0    # how many comics we have successfully stored
    batch = []           # comics read but not yet written to MotherDuck
    batch_size = 500     # write to MotherDuck once the batch reaches this size

    def _read(i: int):
        """Read ONE file from R2. Return the error instead of raising it.

        We must NOT call context.log here, because this runs on a background
        thread and Dagster's logging is not thread-safe.
        """
        try:
            return read_comic_from_r2(s3, i)
        except Exception as e:
            return e

    # pool.map() returns results in the SAME order as the numbers we gave it,
    # so comics are inserted in ascending order.
    with ThreadPoolExecutor(max_workers=20) as pool:
        for i, result in zip(missing_ids, pool.map(_read, missing_ids)):
            if isinstance(result, Exception):
                context.log.warning(f"Could not read comic #{i} from R2: {result}")
                continue

            batch.append(result)

            if len(batch) >= batch_size:
                df = pd.DataFrame(batch)
                insert_comic_to_duckdb(con, df, schema_version=active_schema_version, target_schema=target_schema)
                success_count += len(batch)
                batch = []
                context.log.info(f"Progress: Loaded {success_count} comics into MotherDuck so far (Current ID: #{i})...")

    # Write whatever is left over (the last, smaller-than-500 batch, if any).
    if batch:
        df = pd.DataFrame(batch)
        insert_comic_to_duckdb(con, df, schema_version=active_schema_version, target_schema=target_schema)
        success_count += len(batch)

    con.close()
    context.log.info(
        f"Successfully loaded {success_count} comic(s) into MotherDuck "
        f"using schema version: {active_schema_version}."
    )

    return dg.MaterializeResult()
