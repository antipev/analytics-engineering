#!/usr/bin/env python3
"""Force the monthly Dagster schedule to STOPPED before Dagster starts.

``default_status=STOPPED`` only applies when a schedule has no stored state.
Restoring ``schedules.db`` from an older deployment can preserve ``RUNNING``,
which would let the daemon race ``/wake``. Stop matching schedules by name so
the result is independent of the stored code-location origin.
"""

from __future__ import annotations

import os
import sys

from dagster import DagsterInstance
from dagster._core.scheduler.instigation import InstigatorStatus, InstigatorType

SCHEDULE_NAMES = {
    name.strip()
    for name in os.environ.get(
        "DAGSTER_SCHEDULES_TO_STOP", "comics_ingestion_schedule"
    ).split(",")
    if name.strip()
}


def _log(message: str) -> None:
    print(f"[schedule-stop] {message}", flush=True)


def main() -> int:
    instance = DagsterInstance.get()
    storage = instance.schedule_storage
    if storage is None:
        print(
            "[schedule-stop] ERROR: Dagster instance has no schedule storage",
            file=sys.stderr,
            flush=True,
        )
        return 1

    states = storage.all_instigator_state(
        instigator_type=InstigatorType.SCHEDULE,
        instigator_statuses={
            InstigatorStatus.RUNNING,
            InstigatorStatus.DECLARED_IN_CODE,
        },
    )

    stopped = 0
    for state in states:
        if state.instigator_name not in SCHEDULE_NAMES:
            continue
        storage.update_instigator_state(state.with_status(InstigatorStatus.STOPPED))
        location = state.repository_selector.location_name
        _log(f"stopped {state.instigator_name} (code location {location})")
        stopped += 1

    if stopped == 0:
        _log("no running target schedules; nothing to do")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
