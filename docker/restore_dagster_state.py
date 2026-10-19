#!/usr/bin/env python3
"""Restore Dagster SQLite state from Litestream replicas in R2.

Litestream stores each database as a directory of LTX files, so the replica
URL is the database key (for example ``history/runs.db``), not the local file.
This script restores the top-level databases and every per-run event-log
database in parallel before Dagster starts.

If R2 is not configured, the script exits successfully and Dagster starts with
fresh local SQLite files. Once R2 is configured, restore failures are fatal so
Cloud Run does not silently start with empty run history.
"""

from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote

import boto3

MAX_WORKERS = 8
RESTORE_TIMEOUT_SECONDS = 180


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required to restore Dagster state")
    return value


def _log(message: str) -> None:
    print(f"[restore] {message}", flush=True)


def _replica_url(bucket: str, key: str, endpoint: str) -> str:
    # Percent-encode the endpoint so the HTTPS scheme is unambiguous to
    # Litestream's URL parser. R2 uses the "auto" region.
    return f"s3://{bucket}/{key}?endpoint={quote(endpoint, safe='')}&region=auto"


def _list_common_prefixes(s3, bucket: str, prefix: str) -> list[str]:
    paginator = s3.get_paginator("list_objects_v2")
    prefixes: list[str] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix, Delimiter="/"):
        prefixes.extend(item["Prefix"] for item in page.get("CommonPrefixes", []))
    return prefixes


def _prefix_exists(s3, bucket: str, prefix: str) -> bool:
    response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=1)
    return bool(response.get("Contents") or response.get("CommonPrefixes"))


def _restore_one(litestream: str, url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            litestream,
            "restore",
            "-if-replica-exists",
            "-o",
            str(destination),
            url,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=RESTORE_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"litestream restore failed for {destination}: {detail}")


def main() -> int:
    bucket = os.environ.get("DAGSTER_R2_BUCKET", "").strip()
    prefix = os.environ.get("DAGSTER_R2_PREFIX", "dagster_home").strip().strip("/")

    if not bucket:
        _log("DAGSTER_R2_BUCKET is not set; starting with fresh Dagster state")
        return 0

    account_id = _required("R2_ACCOUNT_ID")
    access_key = _required("R2_ACCESS_KEY_ID")
    secret_key = _required("R2_SECRET_ACCESS_KEY")
    dagster_home = Path(_required("DAGSTER_HOME"))
    litestream = os.environ.get("LITESTREAM_BINARY", "litestream")

    endpoint = f"https://{account_id}.r2.cloudflarestorage.com"
    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
    )

    base = f"{prefix}/" if prefix else ""
    targets: dict[str, Path] = {}

    # Top-level Dagster databases. Check each replica prefix first so an empty
    # bucket is a fast no-op instead of many litestream processes.
    for key, destination in (
        (f"{base}history/runs.db", dagster_home / "history" / "runs.db"),
        (f"{base}history/event_log.db", dagster_home / "history" / "event_log.db"),
        (f"{base}schedules/schedules.db", dagster_home / "schedules" / "schedules.db"),
    ):
        if _prefix_exists(s3, bucket, f"{key}/"):
            targets[key] = destination

    # Per-run event-log databases: history/runs/<run_id>.db/...
    runs_prefix = f"{base}history/runs/"
    for common_prefix in _list_common_prefixes(s3, bucket, runs_prefix):
        relative = common_prefix[len(runs_prefix):].strip("/")
        if relative.endswith(".db"):
            targets[f"{runs_prefix}{relative}"] = (
                dagster_home / "history" / "runs" / relative
            )

    if not targets:
        _log(f"No Litestream replicas found under s3://{bucket}/{base}; starting fresh")
        return 0

    _log(f"Restoring {len(targets)} database(s) from s3://{bucket}/{base}")
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(
                _restore_one,
                litestream,
                _replica_url(bucket, key, endpoint),
                destination,
            ): key
            for key, destination in targets.items()
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                future.result()
                _log(f"restored {key}")
            except Exception as exc:  # noqa: BLE001 - report all failures together
                failures.append(f"{key}: {exc}")

    if failures:
        for failure in failures:
            print(f"[restore] ERROR: {failure}", file=sys.stderr, flush=True)
        return 1

    _log("Dagster state restore complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
