#!/usr/bin/env python3
"""Restore Dagster SQLite state from Litestream replicas in R2.

Litestream stores each database as a directory of LTX files, so the replica
URL is the database key (for example ``history/runs.db``), not the local file.
This script restores the top-level databases and every per-run event-log
database in parallel before Dagster starts.

If R2 is not configured, the script exits successfully and Dagster starts with
fresh local SQLite files. Once R2 is configured, a restore that *fails* is fatal,
so Cloud Run does not silently start with empty run history — but a restore that
succeeds while writing a malformed file is self-healing: `PRAGMA quick_check`
runs on every restored database, and a corrupt one is copied to
``<prefix>/_quarantine/<timestamp>/``, its Litestream replica is deleted, and the
local file is dropped so Dagster starts with an empty database instead of a
broken one. Set ``DAGSTER_RESTORE_SELF_HEAL=0`` to keep the old fail-fast
behaviour.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import boto3

MAX_WORKERS = 8
RESTORE_TIMEOUT_SECONDS = 180
# R2 rate-limits by prefix and returns 429 when two instances restore the same
# objects at once (which happens while Cloud Run retries a failing startup).
RESTORE_ATTEMPTS = 3
RESTORE_RETRY_DELAY_SECONDS = 5
RETRYABLE_RESTORE_ERRORS = (
    "429",
    "SlowDown",
    "ServiceUnavailable",
    "Reduce your concurrent request rate",
    "InternalError",
    "RequestTimeTooSkewed",
)

# A restored file is verified with `PRAGMA quick_check` before Dagster is allowed
# to use it. `DAGSTER_RESTORE_SELF_HEAL=0` keeps the old fail-fast behaviour.
SELF_HEAL_ENV = "DAGSTER_RESTORE_SELF_HEAL"
SELF_HEAL_DEFAULT = True
QUARANTINE_PREFIX = "_quarantine"


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required to restore Dagster state")
    return value


def _log(message: str) -> None:
    print(f"[restore] {message}", flush=True)


def _self_heal_enabled() -> bool:
    """True unless the operator explicitly opts out of quarantining corrupt files."""
    raw = os.environ.get(SELF_HEAL_ENV, "").strip().lower()
    if not raw:
        return SELF_HEAL_DEFAULT
    return raw not in {"0", "false", "no", "off"}


def _quick_check(path: Path) -> str:
    """Return ``ok`` when SQLite can read every page, otherwise a short reason.

    `quick_check` is the cheap sibling of `integrity_check`: it reads all pages
    but skips the index-versus-table cross-checks, which is milliseconds here.
    A database damaged at the page level raises on this call, and a file that is
    not a database at all raises when the header is read.
    """
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except (sqlite3.Error, ValueError) as exc:
        return f"cannot open: {exc}"
    try:
        row = conn.execute("PRAGMA quick_check").fetchone()
    except sqlite3.Error as exc:
        return f"{type(exc).__name__}: {exc}"
    finally:
        conn.close()
    return str(row[0]) if row else "no result"


def _delete_prefix(s3, bucket: str, key_prefix: str) -> int:
    """Delete every object under a Litestream replica prefix; return the count."""
    deleted = 0
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=key_prefix):
        keys = [{"Key": item["Key"]} for item in page.get("Contents", [])]
        if not keys:
            continue
        s3.delete_objects(Bucket=bucket, Delete={"Objects": keys})
        deleted += len(keys)
    return deleted


def _sanitize(text: str, limit: int = 200) -> str:
    """Collapse a SQLite verdict into one ASCII line that can be an HTTP header."""
    single_line = " ".join(str(text).split())
    ascii_only = "".join(ch if 32 <= ord(ch) < 127 else "?" for ch in single_line)
    return (ascii_only[:limit] or "unknown")


def _quarantine_and_reset(
    s3, bucket: str, base: str, key: str, path: Path, reason: str
) -> str:
    """Preserve a corrupt database in R2, drop its replica, and delete the local copy.

    The local file must go: Dagster then creates an empty database, and Litestream
    starts a new replica generation on first write. The old replica objects must go
    too, because a fresh database cannot continue an existing generation.

    ``reason`` comes from ``PRAGMA quick_check`` and is multi-line, so it is
    flattened before it is used as S3 object metadata — an HTTP header cannot
    carry a newline, and boto3 rejects the whole request when it does.
    """
    relative = key[len(base):] if base and key.startswith(base) else key
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    quarantine_key = f"{base}{QUARANTINE_PREFIX}/{stamp}/{relative}"
    s3.upload_file(
        str(path),
        bucket,
        quarantine_key,
        ExtraArgs={"Metadata": {"quick-check": _sanitize(reason)}},
    )
    deleted = _delete_prefix(s3, bucket, f"{key}/")
    path.unlink(missing_ok=True)
    _log(f"quarantined {key} to s3://{bucket}/{quarantine_key} and dropped {deleted} replica object(s)")
    return quarantine_key


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
    last_detail = ""
    for attempt in range(1, RESTORE_ATTEMPTS + 1):
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
        if result.returncode == 0:
            return
        last_detail = (result.stderr or result.stdout).strip()
        retryable = any(marker in last_detail for marker in RETRYABLE_RESTORE_ERRORS)
        if not retryable or attempt == RESTORE_ATTEMPTS:
            break
        _log(
            f"restore of {destination} hit a transient R2 error "
            f"(attempt {attempt}/{RESTORE_ATTEMPTS}); retrying in {RESTORE_RETRY_DELAY_SECONDS}s"
        )
        time.sleep(RESTORE_RETRY_DELAY_SECONDS)
    raise RuntimeError(f"litestream restore failed for {destination}: {last_detail}")


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
    self_heal = _self_heal_enabled()
    if not self_heal:
        _log(f"{SELF_HEAL_ENV} is off; a corrupt database will fail the boot")
    failures: list[str] = []
    corrupt: list[tuple[str, Path, str]] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(
                _restore_one,
                litestream,
                _replica_url(bucket, key, endpoint),
                destination,
            ): (key, destination)
            for key, destination in targets.items()
        }
        for future in as_completed(futures):
            key, destination = futures[future]
            try:
                future.result()
            except Exception as exc:  # noqa: BLE001 - report all failures together
                failures.append(f"{key}: {exc}")
                continue

            # A restore that exits 0 can still write a malformed file: Litestream
            # does not verify content. Ask SQLite before Dagster trusts it.
            verdict = _quick_check(destination)
            if verdict.lower() == "ok":
                _log(f"restored {key} (quick_check ok)")
                continue
            if not self_heal:
                failures.append(f"{key}: corrupt ({_sanitize(verdict)}) and {SELF_HEAL_ENV}=0")
                continue
            corrupt.append((key, destination, verdict))

    # Quarantine only after every restore has finished. R2 rate-limits by prefix
    # and answers 429 "reduce your concurrent request rate for the same object"
    # when our list/delete calls race the restores still in flight.
    quarantined: list[tuple[str, str]] = []
    for key, destination, verdict in corrupt:
        try:
            _quarantine_and_reset(s3, bucket, base, key, destination, verdict)
            quarantined.append((key, verdict))
        except Exception as exc:  # noqa: BLE001 - keep booting, but say so
            failures.append(
                f"{key}: corrupt ({_sanitize(verdict)}) and quarantine failed: {_sanitize(exc)}"
            )

    if quarantined:
        _log(
            "WARNING: started with empty state for "
            + ", ".join(key for key, _ in quarantined)
            + " — the previous copy was corrupt and has been quarantined"
        )

    if failures:
        for failure in failures:
            print(f"[restore] ERROR: {failure}", file=sys.stderr, flush=True)
        return 1

    _log("Dagster state restore complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
