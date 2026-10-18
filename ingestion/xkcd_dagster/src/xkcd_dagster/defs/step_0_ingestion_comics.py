
# Imports the core Dagster framework.
import dagster as dg

# Imports the Pandas library for tabular data structures.
import pandas as pd

# Imports the requests library for making HTTP API calls.
import requests

# Imports boto3 (AWS S3 SDK). Cloudflare R2 speaks the S3 API, so we use it to talk to R2.
import boto3

# Imports JSON for parsing our schema configuration files and writing comic files.
import json

# Imports OS to read credentials from environment variables.
import os

# Imports Python's built-in thread pool. We use it to download and upload many
# XKCD comics at the same time instead of one after another.
from concurrent.futures import ThreadPoolExecutor

# Imports environment loader for R2 credentials.
from dotenv import load_dotenv


#----------------------------------------------------------------------
# Load environment variables from .env file
load_dotenv()
#----------------------------------------------------------------------

# Name of the Cloudflare R2 bucket where each comic is stored as its own file.
R2_BUCKET = "xkcd-ingest"

# "Folder" inside the bucket where the comic files are saved.
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
# Function 3: Save each comic as a file in R2
# ---------------------------------------------------------------------
def save_comics_to_r2(s3, batch: list) -> int:
    """Uploads each comic in the batch as its own JSON file to R2.

    No schema validation: R2 is a raw landing zone, so whatever the XKCD
    API returns is stored as-is. Returns how many files were uploaded.
    """
    def _upload(record: dict):
        """Upload ONE comic file. Return the error instead of raising it."""
        try:
            key = f"{R2_PREFIX}/{int(record['num'])}.json"
            s3.put_object(
                Bucket=R2_BUCKET,
                Key=key,
                Body=json.dumps(record).encode("utf-8"),
                ContentType="application/json",
            )
            return None
        except Exception as e:
            return e

    uploaded = 0
    with ThreadPoolExecutor(max_workers=20) as pool:
        for result in pool.map(_upload, batch):
            if result is None:
                uploaded += 1
            else:
                raise result
    return uploaded


# ---------------------------------------------------------------------
# Dagster Asset: Orchestrates Incremental Ingestion & Gap Filling
# ---------------------------------------------------------------------
class RefreshConfig(dg.Config):
    # Set True in the Dagster UI to re-download every comic, ignoring what is in R2.
    full_refresh: bool = False


@dg.asset(key="raw_comics", group_name="comics", kinds={"python"})
# - `key="raw_comics"` -> stable asset ID for the R2 landing zone, independent
#   of any DuckDB table or schema version. Without it, the key would be the
#   function name (`step_0_ingestion_comics`).
# - `group_name="comics"` -> puts the asset into the "comics" group in the UI.
#   It has no lineage edge to `raw_comics_v2`; that asset stays owned by step_1.

def step_0_ingestion_comics(context: dg.AssetExecutionContext, config: RefreshConfig) -> dg.MaterializeResult:
    """Backfill any missing XKCD comics into Cloudflare R2.

    Each comic is saved as its own file: raw_comics/<num>.json in the
    xkcd-ingest bucket. We fetch many comics over HTTP at the same time
    (in parallel) instead of one after another.
    """
    # 1. Open a connection to Cloudflare R2.
    s3 = get_r2_client()

    # 2. Read the comic numbers we already have stored in R2, so we only
    #    download the gaps. Each file is named <num>.json, so the number is
    #    the file name without the extension.
    existing_set = set()
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=R2_BUCKET, Prefix=f"{R2_PREFIX}/"):
        for obj in page.get("Contents", []):
            file_name = obj["Key"].split("/")[-1]
            if file_name.endswith(".json"):
                stem = file_name[:-len(".json")]
                if stem.isdigit():
                    existing_set.add(int(stem))

    # Full refresh: pretend nothing is stored, so every comic is downloaded
    # again and its file in R2 is overwritten.
    if config.full_refresh:
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

    context.log.info(f"Comics in R2: {len(existing_set)}. Missing to fetch: {len(missing_ids)}.")

    # If nothing is missing, we are already up to date, so stop here.
    if not missing_ids:
        context.log.info("Bucket is fully up to date! No missing comics to fetch.")
        return dg.MaterializeResult()

    # 5. Download the missing comics in parallel, then save them in batches.
    #
    #    A "batch" is a list of comic dictionaries we collect in memory and
    #    save together (500 at a time).
    #
    #    "max_workers" is how many downloads run at the same time. 20 is a
    #    good balance: fast, but still polite to the XKCD server.
    success_count = 0    # how many comics we have successfully stored
    batch = []           # comics collected but not yet saved to R2
    batch_size = 500     # save to R2 once the batch reaches this size

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
    # numbers we gave it, so comics are saved in ascending order.
    with ThreadPoolExecutor(max_workers=20) as pool:
        for i, result in zip(missing_ids, pool.map(_fetch, missing_ids)):
            # If the download failed, _fetch returned the exception -> log it
            # and move on to the next comic.
            if isinstance(result, Exception):
                context.log.warning(f"Could not fetch comic #{i}: {result}")
                continue

            batch.append(result)

            # When the batch is full, save it to R2 and start a new one.
            if len(batch) >= batch_size:
                success_count += save_comics_to_r2(s3, batch)
                batch = []
                context.log.info(f"Progress: Successfully ingested {success_count} comics so far (Current ID: #{i})...")

    # Save whatever is left over (the last, smaller-than-500 batch, if any).
    if batch:
        success_count += save_comics_to_r2(s3, batch)

    context.log.info(
        f"Successfully backfilled/fetched {success_count} missing comic(s) "
        f"into R2 bucket '{R2_BUCKET}'."
    )

    return dg.MaterializeResult()
