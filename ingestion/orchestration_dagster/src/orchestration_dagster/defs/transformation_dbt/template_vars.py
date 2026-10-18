import os
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Optional

import dagster as dg


# --- Shared dbt resolution (single source of truth) ---
_EXCLUDED_DIRS = {
    ".venv", ".git", "logs", "target", "dbt_packages",
    "__pycache__", ".local_defs_state", ".dg",
}


def find_dbt_project_dir() -> Path:
    """Locate the dbt project root by finding its ``dbt_project.yml``.

    Walks up from this file and searches for ``dbt_project.yml``, skipping
    venv/git/packages/artifacts — so it's automatic and independent of the
    absolute checkout location.
    """
    for parent in Path(__file__).resolve().parents:
        for root, dirs, files in os.walk(parent):
            dirs[:] = [d for d in dirs if d not in _EXCLUDED_DIRS and not d.startswith(".tmp")]
            if "dbt_project.yml" in files:
                return Path(root)
    raise RuntimeError("Could not locate dbt_project.yml")


DBT_PROJECT_DIR = find_dbt_project_dir()
MODELS_DIR = DBT_PROJECT_DIR / "models"
# DBT_TARGET = os.getenv("DBT_TARGET", "duckdb_dev")     # Local DuckDB
DBT_TARGET = os.getenv("DBT_TARGET", "motherduck_dev")   # MotherDuck


@dg.template_var
def group_from_fqn() -> Callable[[Sequence[str]], str | None]:
    """Returns a function that extracts the group name from a dbt model's fqn (fully qualified name).

    The fqn contains the directory structure, e.g.:
    ["jaffle_shop", "staging", "stg_customers"] -> returns "staging"
    ["jaffle_shop", "marts", "customers"] -> returns "marts"
    """

    def _get_group(fqn: Sequence[str]) -> str | None:
        # fqn structure: [project_name, folder, ..., model_name]
        # We want the first folder after the project name
        if len(fqn) >= 2:
            return fqn[1]  # Returns models level 1: "comics", "jaffle-shop"; or level 2: "staging", "intermediate", "marts", etc.
        return None

    return _get_group