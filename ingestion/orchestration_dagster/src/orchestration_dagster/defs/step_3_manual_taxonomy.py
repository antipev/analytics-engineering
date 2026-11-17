"""On-demand DeepSeek refresh of the comics category taxonomy.

The dbt model this asset runs is deliberately flag-gated *off*
(``DBT_DISCOVER_COMIC_CATEGORIES=false``), so nothing else — not a plain ``dbt build``,
not CI, not the monthly ``comics_transformation_job`` — can select it. This module is
the one sanctioned way to run it in production.

The asset sits in group ``manual`` on purpose: ``step_2_transformation_dbt.py`` builds
``<domain>_transformation_job`` from ``AssetSelection.groups(domain)``, so an asset in
group ``comics`` would be swept into the sensor-triggered monthly run and would spend
money (and overwrite the reviewed table) on every build.

See DOCUMENTATION/2_Plan_and_Implementation/13_PROJECT_1_Comics_Classification.md §8.
"""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import dagster as dg

from orchestration_dagster.defs.transformation_dbt.template_vars import (
    DBT_PROJECT_DIR,
    DBT_TARGET,
)

SELECTION = "stg_comics_categories"
ASSET_NAME = "comic_category_taxonomy"

# Console script first, then the script that sits next to the running interpreter, so
# the same code works from an activated venv locally and from the image's PATH.
DBT_BIN = shutil.which("dbt") or str(Path(sys.executable).with_name("dbt"))


class TaxonomyRefreshConfig(dg.Config):
    """Launch config. ``reason`` is required on purpose.

    A required field means an accidental "materialize all" fails validation in
    milliseconds and never reaches DeepSeek; the value is echoed into run metadata so
    every paid run has a stated justification.
    """

    reason: str


@dg.asset(
    name=ASSET_NAME,
    group_name="manual",
    deps=[dg.AssetKey("stg_comics")],
    kinds={"dbt", "deepseek"},
    description=(
        "On-demand DeepSeek refresh of staging.stg_comics_categories. Paid (~$0.15) "
        "and non-deterministic: it OVERWRITES the reviewed taxonomy, so launch it only "
        "when the category list is deliberately being replaced."
    ),
)
def comic_category_taxonomy(
    context: dg.AssetExecutionContext, config: TaxonomyRefreshConfig
) -> dg.MaterializeResult:
    if not os.getenv("DEEPSEEK_API_KEY"):
        raise dg.Failure(
            description=(
                "DEEPSEEK_API_KEY is not set for this process. In Cloud Run it comes "
                "from --set-secrets (deepseek-api-key); locally, export it from .env."
            )
        )

    # The flag lives only in the child environment: the Dagster process keeps it unset,
    # so the dbt manifest used by every other asset still has the model disabled.
    env = {**os.environ, "DBT_DISCOVER_COMIC_CATEGORIES": "true"}
    command = [
        DBT_BIN,
        "build",
        "--target",
        DBT_TARGET,
        "--profiles-dir",
        str(DBT_PROJECT_DIR),
        "--select",
        SELECTION,
    ]

    context.log.info("Running %s (reason: %s)", " ".join(command), config.reason)
    started = time.time()
    proc = subprocess.run(
        command,
        cwd=str(DBT_PROJECT_DIR),
        env=env,
        capture_output=True,
        text=True,
    )
    elapsed = round(time.time() - started, 1)
    tail = "\n".join((proc.stdout + proc.stderr).splitlines()[-25:])
    context.log.info(tail)

    if proc.returncode != 0:
        raise dg.Failure(
            description=f"dbt build --select {SELECTION} failed after {elapsed}s",
            metadata={"reason": config.reason, "dbt_output_tail": dg.MetadataValue.text(tail)},
        )

    return dg.MaterializeResult(
        metadata={
            "reason": config.reason,
            "selection": SELECTION,
            "dbt_target": DBT_TARGET,
            "duration_seconds": elapsed,
            "dbt_output_tail": dg.MetadataValue.text(tail),
        }
    )


# No schedule, no sensor: the only way this job runs is a human launching it.
comic_category_taxonomy_job = dg.define_asset_job(
    name="comic_category_taxonomy_job",
    selection=dg.AssetSelection.assets(ASSET_NAME),
    description=(
        "Manual-only. Rebuilds the DeepSeek category taxonomy (~$0.15, ~5 min) and "
        "overwrites staging.stg_comics_categories. Never scheduled."
    ),
    tags={"trigger": "manual"},
)
