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
``<prefix>/_quarantine/<timestamp>/`` and its local file is dropped so Dagster
starts with an empty database instead of a broken one. A replica Litestream
cannot decode at all (``decode database: decode page N``) is treated the same
way. Either case bumps the epoch pointer ``<prefix>/_epoch.json``: every replica
lives under ``<prefix>/<epoch>/…``, so a fresh epoch starts empty while the old
objects stay untouched as an archive. Set ``DAGSTER_RESTORE_SELF_HEAL=0`` to keep
the old fail-fast behaviour.
"""

from __future__ import annotations

import json
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
# Every replica lives under <prefix>/<epoch>/…, and <prefix>/_epoch.json names the
# epoch that is live. A corrupt database moves the pointer instead of deleting
# objects: deleting a prefix while another instance is still replicating to it
# leaves deltas with no base snapshot, and Litestream then fails to decode the
# replica at the next boot (F7, §7B.2.1).
EPOCH_OBJECT = "_epoch.json"
EPOCH_ENV = "DAGSTER_REPLICA_EPOCH"
EPOCH_FILE_ENV = "DAGSTER_REPLICA_EPOCH_FILE"
EPOCH_DEFAULT = "g0"
# A replica can be unreadable *before* it ever becomes a file: Litestream decodes
# the LTX stream and fails with "decode database: decode page N". That happens
# when a replica prefix is deleted while another live instance is still
# replicating to it, mixing generations. There is nothing to quarantine in that
# case — the bytes never reached this container — so the prefix is discarded and
# the database starts empty, which is the same deal as a corrupt file.
CONTENT_ERROR_MARKERS = (
    "decode database",
    "decode page",
    "checksum",
    "invalid database",
    "file is not a database",
    "no such object",
)


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required to restore Dagster state")
    return value


def _is_per_run_db(relative: str) -> bool:
    """True for a per-run event-log database key (``<run_id>.db``).

    Litestream's directory watcher also emits a replica whose name is the bare
    suffix ``.db`` — the empty stem left when it treats ``history/runs`` itself as
    a database. Restoring it writes a file literally named ``.db``, which Litestream
    then replicates again, so the artifact survives every boot and reproduces itself.
    """
    return relative.endswith(".db") and relative != ".db"


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


def _with_retry(action, description: str):
    """Run a small R2 call, retrying the rate-limit errors R2 is known for."""
    last_error: Exception | None = None
    for attempt in range(1, RESTORE_ATTEMPTS + 1):
        try:
            return action()
        except Exception as exc:  # noqa: BLE001 - re-raised below when not retryable
            detail = f"{type(exc).__name__}: {exc}"
            if not any(marker in detail for marker in RETRYABLE_RESTORE_ERRORS):
                raise
            last_error = exc
            _log(
                f"{description} hit a transient R2 error (attempt {attempt}/{RESTORE_ATTEMPTS})"
            )
            time.sleep(RESTORE_RETRY_DELAY_SECONDS)
    raise RuntimeError(f"{description} failed after {RESTORE_ATTEMPTS} attempts: {last_error}")


def _read_epoch(s3, bucket: str, prefix: str) -> str | None:
    """Return the replica epoch R2 points at, or ``None`` when no pointer exists.

    ``None`` means the bucket still uses the pre-epoch layout (``<prefix>/history``
    with no epoch directory). The caller then restores from that layout and writes
    a new pointer, so the next replica generation lands in an epoch directory
    without any object ever being deleted.
    """
    key = f"{prefix}/{EPOCH_OBJECT}" if prefix else EPOCH_OBJECT

    def fetch():
        try:
            return s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        except s3.exceptions.NoSuchKey:
            return None
        except Exception as exc:  # noqa: BLE001 - only a 404 means "no pointer"
            code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
            if code in {"NoSuchKey", "404", "NoSuchBucket"}:
                return None
            raise

    body = _with_retry(fetch, f"reading {key}")
    if not body:
        return None
    return str(json.loads(body).get("epoch", "")).strip() or None


def _write_epoch(s3, bucket: str, prefix: str, epoch: str, only_if_missing: bool) -> None:
    """Point R2 at ``epoch``; Litestream writes new replicas under it."""
    key = f"{prefix}/{EPOCH_OBJECT}" if prefix else EPOCH_OBJECT
    if only_if_missing and _read_epoch(s3, bucket, prefix) is not None:
        return
    payload = json.dumps(
        {
            "epoch": epoch,
            "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    ).encode()
    _with_retry(
        lambda: s3.put_object(Bucket=bucket, Key=key, Body=payload),
        f"writing {key}",
    )


def _claim_epoch(s3, bucket: str, prefix: str, fallback: str) -> str:
    """Create the epoch pointer if it is missing; return the epoch now in force."""
    _write_epoch(s3, bucket, prefix, fallback, only_if_missing=True)
    return _read_epoch(s3, bucket, prefix) or fallback


def _bump_epoch(s3, bucket: str, prefix: str) -> str:
    """Move the pointer to a new, empty epoch — the whole of a self-heal."""
    epoch = datetime.now(timezone.utc).strftime("g%Y%m%dT%H%M%SZ")
    _write_epoch(s3, bucket, prefix, epoch, only_if_missing=False)
    return epoch


def _epoch_file() -> Path:
    return Path(os.environ.get(EPOCH_FILE_ENV, "/tmp/dagster_replica_epoch"))


def _record_epoch(epoch: str) -> None:
    """Hand the epoch to the entrypoint, which passes it to Litestream."""
    _epoch_file().write_text(f"{epoch}\n")


def _sanitize(text: str, limit: int = 200) -> str:
    """Collapse a SQLite verdict into one ASCII line that can be an HTTP header."""
    single_line = " ".join(str(text).split())
    ascii_only = "".join(ch if 32 <= ord(ch) < 127 else "?" for ch in single_line)
    return (ascii_only[:limit] or "unknown")


def _quarantine(s3, bucket: str, base: str, key: str, path: Path, reason: str) -> str:
    """Copy a corrupt database to R2, then delete the local file.

    The local file must go: Dagster then creates an empty database, and Litestream
    starts a new replica generation under the next epoch. Nothing is deleted in R2
    — the caller moves the epoch pointer, which leaves the old objects as an
    archive instead of invalidating a replica that another instance may still be
    writing to.

    ``reason`` comes from ``PRAGMA quick_check`` and is multi-line, so it is
    flattened before it is used as S3 object metadata — an HTTP header cannot
    carry a newline, and boto3 rejects the whole request when it does.
    """
    relative = key[len(base):] if base and key.startswith(base) else key
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    quarantine_key = f"{base}{QUARANTINE_PREFIX}/{stamp}/{relative}"
    _with_retry(
        lambda: s3.upload_file(
            str(path),
            bucket,
            quarantine_key,
            ExtraArgs={"Metadata": {"quick-check": _sanitize(reason)}},
        ),
        f"quarantining {key}",
    )
    path.unlink(missing_ok=True)
    _log(f"quarantined {key} to s3://{bucket}/{quarantine_key}")
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


def _is_replica_content_error(detail: str) -> bool:
    lowered = detail.lower()
    return any(marker in lowered for marker in CONTENT_ERROR_MARKERS)


def _reset_replica(path: Path, detail: str, key: str) -> None:
    """Drop a replica that cannot be decoded, plus any partial file it left."""
    path.unlink(missing_ok=True)
    _log(
        f"WARNING: discarded undecodable replica {key} "
        f"({_sanitize(detail, 120)}); starting with empty state"
    )


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

    # The epoch decides both where replicas are read from and where Litestream
    # writes them. No pointer (= None) means the pre-epoch layout; we restore from
    # it and then move the pointer, so the migration deletes nothing.
    read_epoch = _read_epoch(s3, bucket, prefix)
    base = f"{prefix}/{read_epoch}/" if read_epoch else (f"{prefix}/" if prefix else "")
    write_epoch = read_epoch or _claim_epoch(s3, bucket, prefix, EPOCH_DEFAULT)
    _record_epoch(write_epoch)
    if read_epoch is None:
        _log(
            f"No {EPOCH_OBJECT} under s3://{bucket}/{prefix or ''}; restoring the "
            f"legacy layout and moving new replicas to epoch {write_epoch}"
        )
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
        if _is_per_run_db(relative):
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
    undecodable: list[tuple[str, Path, str]] = []
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
                detail = str(exc)
                if self_heal and _is_replica_content_error(detail):
                    undecodable.append((key, destination, detail))
                else:
                    failures.append(f"{key}: {detail}")
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
    # when our list/upload calls race the restores still in flight.
    quarantined: list[tuple[str, str]] = []
    for key, destination, verdict in corrupt:
        try:
            _quarantine(s3, bucket, base, key, destination, verdict)
            quarantined.append((key, verdict))
        except Exception as exc:  # noqa: BLE001 - keep booting, but say so
            failures.append(
                f"{key}: corrupt ({_sanitize(verdict)}) and quarantine failed: {_sanitize(exc)}"
            )

    discarded: list[str] = []
    for key, destination, detail in undecodable:
        try:
            _reset_replica(destination, detail, key)
            discarded.append(key)
        except Exception as exc:  # noqa: BLE001 - keep booting, but say so
            failures.append(f"{key}: replica undecodable and reset failed: {_sanitize(exc)}")

    if quarantined:
        _log(
            "WARNING: started with empty state for "
            + ", ".join(key for key, _ in quarantined)
            + " — the previous copy was corrupt and has been quarantined"
        )
    if discarded:
        _log(
            "WARNING: started with empty state for "
            + ", ".join(discarded)
            + " — the previous replica could not be decoded and has been discarded"
        )

    if quarantined or discarded:
        # Move every database to a fresh epoch: the old objects stay untouched for
        # forensics, and no live instance can corrupt the new generation because it
        # is still writing to the old epoch.
        healed_epoch = _bump_epoch(s3, bucket, prefix)
        _record_epoch(healed_epoch)
        _log(
            f"replicas moved to epoch {healed_epoch}; Litestream starts a new "
            f"generation there and the previous epoch is left as an archive"
        )

    if failures:
        for failure in failures:
            print(f"[restore] ERROR: {failure}", file=sys.stderr, flush=True)
        return 1

    _log("Dagster state restore complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
