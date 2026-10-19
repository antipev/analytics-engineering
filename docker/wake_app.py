#!/usr/bin/env python3
"""Cloud Scheduler wake endpoint for the monthly comics pipeline.

POST /wake idempotently launches comics_ingestion_job, waits for success, then
waits for the sensor-triggered comics_transformation_job. GET /wake/status is a
read-only dead-man's-switch that returns 200 only when both runs succeeded.
The Dagster daemon schedules are STOPPED; this app is the only monthly trigger.
"""

from __future__ import annotations

import fcntl
import hmac
import json
import os
import re
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

GRAPHQL_URL = os.environ.get("DAGSTER_GRAPHQL_URL", "http://127.0.0.1:3000/graphql")
INGESTION_JOB = os.environ.get("DAGSTER_INGESTION_JOB", "comics_ingestion_job")
TRANSFORMATION_JOB = os.environ.get("DAGSTER_TRANSFORMATION_JOB", "comics_transformation_job")
WAKE_SECRET = os.environ.get("WAKE_SHARED_SECRET", "").strip()
WAKE_TIMEOUT_SECONDS = int(os.environ.get("WAKE_TIMEOUT_SECONDS", "1500"))
POLL_SECONDS = float(os.environ.get("WAKE_POLL_INTERVAL_SECONDS", "10"))
LOCK_PATH = "/tmp/dagster-wake.lock"

TERMINAL_STATUSES = {"SUCCESS", "FAILURE", "CANCELED"}
MONTH_RE = re.compile(r"^\d{4}-\d{2}$")

REPOSITORIES_QUERY = """
query WakeRepositories {
  repositoriesOrError {
    __typename
    ... on RepositoryConnection {
      nodes {
        name
        location { name }
        pipelines { name }
      }
    }
    ... on PythonError { message }
  }
}
"""

RUNS_QUERY = """
query WakeRuns($filter: RunsFilter, $limit: Int) {
  runsOrError(filter: $filter, limit: $limit) {
    __typename
    ... on Runs {
      results {
        runId
        jobName
        status
        creationTime
        startTime
        endTime
        tags { key value }
      }
    }
    ... on InvalidPipelineRunsFilterError { message }
    ... on PythonError { message }
  }
}
"""

LAUNCH_QUERY = """
mutation WakeLaunch($executionParams: ExecutionParams!) {
  launchRun(executionParams: $executionParams) {
    __typename
    ... on LaunchRunSuccess { run { runId status } }
    ... on PythonError { message }
  }
}
"""


class WakeError(RuntimeError):
    """A recoverable wake/status failure that should become HTTP 503."""

    def __init__(self, reason: str, message: str, **details: Any) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.details = details


def log_event(event: str, severity: str = "INFO", **fields: Any) -> None:
    print(json.dumps({"event": event, "severity": severity, **fields}, default=str), flush=True)


if not WAKE_SECRET:
    log_event("wake_secret_missing", severity="ERROR")


def _graphql(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        response = httpx.post(
            GRAPHQL_URL,
            json={"query": query, "variables": variables or {}},
            timeout=30.0,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:  # noqa: BLE001 - convert transport errors into a wake error
        raise WakeError("dagster_unreachable", f"Dagster GraphQL request failed: {exc}") from exc

    if payload.get("errors"):
        raise WakeError("dagster_graphql_error", str(payload["errors"]))
    return payload.get("data") or {}


def _runs(filter_: dict[str, Any], limit: int = 50) -> list[dict[str, Any]]:
    data = _graphql(RUNS_QUERY, {"filter": filter_, "limit": limit})
    result = data.get("runsOrError", {})
    if result.get("__typename") != "Runs":
        raise WakeError(
            "dagster_runs_query_failed",
            result.get("message", f"Unexpected runsOrError result: {result.get('__typename')}"),
        )
    return list(result.get("results", []))


def _find_run(job_name: str, tags: dict[str, str]) -> dict[str, Any] | None:
    runs = _runs(
        {
            "pipelineName": job_name,
            "tags": [{"key": key, "value": value} for key, value in tags.items()],
        }
    )
    if not runs:
        return None
    return max(runs, key=lambda run: run.get("creationTime") or 0)


def _find_transformation(ingestion: dict[str, Any]) -> dict[str, Any] | None:
    created_after = ingestion.get("startTime") or ingestion.get("creationTime") or 0
    runs = _runs(
        {
            "pipelineName": TRANSFORMATION_JOB,
            "tags": [{"key": "triggered_by", "value": "raw_comics_v2"}],
        }
    )
    correlated = [run for run in runs if (run.get("creationTime") or 0) >= created_after]
    if not correlated:
        return None
    return max(correlated, key=lambda run: run.get("creationTime") or 0)


def _get_run(run_id: str) -> dict[str, Any] | None:
    runs = _runs({"runIds": [run_id]}, limit=1)
    return runs[0] if runs else None


def _resolve_job(job_name: str) -> tuple[str, str]:
    data = _graphql(REPOSITORIES_QUERY)
    connection = data.get("repositoriesOrError", {})
    if connection.get("__typename") != "RepositoryConnection":
        raise WakeError(
            "dagster_repository_error",
            connection.get("message", "Dagster repositories are not available"),
        )
    for repository in connection.get("nodes", []):
        for pipeline in repository.get("pipelines", []):
            if pipeline.get("name") == job_name:
                return repository["location"]["name"], repository["name"]
    raise WakeError("job_not_found", f"Dagster job {job_name!r} was not found")


def _launch_job(job_name: str, month: str) -> str:
    location_name, repository_name = _resolve_job(job_name)
    data = _graphql(
        LAUNCH_QUERY,
        {
            "executionParams": {
                "selector": {
                    "repositoryLocationName": location_name,
                    "repositoryName": repository_name,
                    "jobName": job_name,
                },
                "runConfigData": {},
                "executionMetadata": {
                    "tags": [
                        {"key": "trigger", "value": "cloud-scheduler"},
                        {"key": "scheduled_month", "value": month},
                    ]
                },
            }
        },
    )
    result = data.get("launchRun", {})
    if result.get("__typename") != "LaunchRunSuccess":
        raise WakeError(
            "launch_failed",
            result.get("message", f"Dagster launchRun returned {result.get('__typename')}"),
        )
    return result["run"]["runId"]


def _wait_for_run(run_id: str, deadline: float) -> dict[str, Any]:
    while True:
        run = _get_run(run_id)
        if run is None:
            raise WakeError("run_missing", f"Dagster run {run_id} disappeared")
        if run.get("status") in TERMINAL_STATUSES:
            return run
        if time.monotonic() >= deadline:
            raise WakeError(
                "run_timeout",
                f"Run {run_id} did not finish before the wake timeout",
                run_id=run_id,
                status=run.get("status"),
            )
        time.sleep(min(POLL_SECONDS, max(0.1, deadline - time.monotonic())))


def _wait_for_transformation(ingestion: dict[str, Any], deadline: float) -> dict[str, Any]:
    while True:
        transformation = _find_transformation(ingestion)
        if transformation is not None:
            return _wait_for_run(transformation["runId"], deadline)
        if time.monotonic() >= deadline:
            raise WakeError(
                "transformation_not_started",
                "The raw_comics_v2 asset sensor did not start a transformation run",
                ingestion_run_id=ingestion["runId"],
            )
        time.sleep(min(POLL_SECONDS, max(0.1, deadline - time.monotonic())))


def _run_summary(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": run.get("runId"),
        "job_name": run.get("jobName"),
        "status": run.get("status"),
        "creation_time": run.get("creationTime"),
        "start_time": run.get("startTime"),
        "end_time": run.get("endTime"),
    }


def _current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _requested_month(request: Request) -> str:
    month = request.query_params.get("month") or _current_month()
    if not MONTH_RE.fullmatch(month):
        raise ValueError("month must use YYYY-MM format")
    return month


def _authorized(request: Request) -> bool:
    supplied = request.headers.get("x-wake-secret", "")
    return bool(WAKE_SECRET) and hmac.compare_digest(supplied, WAKE_SECRET)


@contextmanager
def _launch_lock() -> Iterator[None]:
    # Serializes find-or-launch on this single Cloud Run instance. Cloud Run is
    # capped at max-instances=1, so this also serializes the whole service.
    with open(LOCK_PATH, "w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def _error_response(exc: WakeError, event: str, month: str | None = None) -> JSONResponse:
    fields = {"reason": exc.reason, "message": exc.message, **exc.details}
    if month:
        fields["month"] = month
    log_event(event, severity="ERROR", **fields)
    return JSONResponse({"ok": False, **fields}, status_code=503)


async def healthz(_: Request) -> JSONResponse:
    return JSONResponse({"ok": True})


def wake(request: Request) -> JSONResponse:
    if not _authorized(request):
        log_event("wake_auth_failed", severity="WARNING")
        return JSONResponse({"ok": False, "reason": "unauthorized"}, status_code=401)

    try:
        month = _requested_month(request)
    except ValueError as exc:
        return JSONResponse(
            {"ok": False, "reason": "invalid_month", "message": str(exc)},
            status_code=400,
        )

    deadline = time.monotonic() + WAKE_TIMEOUT_SECONDS
    try:
        with _launch_lock():
            ingestion = _find_run(INGESTION_JOB, {"scheduled_month": month})
            if ingestion is None:
                run_id = _launch_job(INGESTION_JOB, month)
                log_event("wake_run_launched", month=month, job=INGESTION_JOB, run_id=run_id)
                ingestion = _get_run(run_id)
                if ingestion is None:
                    raise WakeError("run_missing", f"Launched run {run_id} was not found")
            else:
                log_event(
                    "wake_run_reused",
                    month=month,
                    job=INGESTION_JOB,
                    run_id=ingestion["runId"],
                    status=ingestion.get("status"),
                )

        ingestion = _wait_for_run(ingestion["runId"], deadline)
        if ingestion.get("status") != "SUCCESS":
            raise WakeError(
                "ingestion_failed",
                f"Ingestion run {ingestion['runId']} finished with {ingestion.get('status')}",
                ingestion_run_id=ingestion["runId"],
                ingestion_status=ingestion.get("status"),
            )

        transformation = _wait_for_transformation(ingestion, deadline)
        if transformation.get("status") != "SUCCESS":
            raise WakeError(
                "transformation_failed",
                f"Transformation run {transformation['runId']} finished with {transformation.get('status')}",
                ingestion_run_id=ingestion["runId"],
                transformation_run_id=transformation["runId"],
                transformation_status=transformation.get("status"),
            )

        log_event(
            "wake_run_completed",
            month=month,
            ingestion_run_id=ingestion["runId"],
            transformation_run_id=transformation["runId"],
        )
        return JSONResponse(
            {
                "ok": True,
                "month": month,
                "ingestion": _run_summary(ingestion),
                "transformation": _run_summary(transformation),
            }
        )
    except WakeError as exc:
        return _error_response(exc, "wake_run_failed", month)


def wake_status(request: Request) -> JSONResponse:
    if not _authorized(request):
        log_event("wake_status_auth_failed", severity="WARNING")
        return JSONResponse({"ok": False, "reason": "unauthorized"}, status_code=401)

    try:
        month = _requested_month(request)
    except ValueError as exc:
        return JSONResponse(
            {"ok": False, "reason": "invalid_month", "message": str(exc)},
            status_code=400,
        )

    try:
        ingestion = _find_run(INGESTION_JOB, {"scheduled_month": month})
        if ingestion is None:
            raise WakeError("missing_ingestion", f"No ingestion run exists for {month}")
        if ingestion.get("status") != "SUCCESS":
            raise WakeError(
                "ingestion_not_successful",
                f"Ingestion run {ingestion['runId']} is {ingestion.get('status')}",
                ingestion_run_id=ingestion["runId"],
                ingestion_status=ingestion.get("status"),
            )

        transformation = _find_transformation(ingestion)
        if transformation is None:
            raise WakeError(
                "missing_transformation",
                "No sensor-triggered transformation run exists for the month",
                ingestion_run_id=ingestion["runId"],
            )
        if transformation.get("status") != "SUCCESS":
            raise WakeError(
                "transformation_not_successful",
                f"Transformation run {transformation['runId']} is {transformation.get('status')}",
                ingestion_run_id=ingestion["runId"],
                transformation_run_id=transformation["runId"],
                transformation_status=transformation.get("status"),
            )

        return JSONResponse(
            {
                "ok": True,
                "month": month,
                "ingestion": _run_summary(ingestion),
                "transformation": _run_summary(transformation),
            }
        )
    except WakeError as exc:
        return _error_response(exc, "wake_status_failed", month)


app = Starlette(
    routes=[
        Route("/healthz", healthz),
        Route("/wake", wake, methods=["POST"]),
        Route("/wake/status", wake_status, methods=["GET"]),
    ]
)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=3001, log_level="info")




