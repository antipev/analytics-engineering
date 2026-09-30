import dagster as dg
from dagster_dbt import DbtCliResource, DbtProject
from xkcd_dagster.defs.transformation_dbt.template_vars import DBT_PROJECT_DIR, DBT_TARGET

dbt_project = DbtProject(project_dir=DBT_PROJECT_DIR, target=DBT_TARGET)

SEEDS = [
    "raw_customers",
    "raw_orders",
    "raw_items",
    "raw_stores",
    "raw_products",
    "raw_supplies",
]


class SeedConfig(dg.Config):
    """Runtime config for the seed (ingestion) assets."""
    full_refresh: bool = False   # -> dbt seed --full-refresh


def _seed_asset(name: str, deps: list[dg.AssetKey] | None = None):
    @dg.asset(
        key=name,
        group_name="jaffle_shop",
        kinds={"dbt"},
        config_schema=SeedConfig.to_fields_dict(),   # exposes full_refresh in the UI
        deps=deps or [],                             # serialize seeds (avoid concurrent CREATE SCHEMA)
    )
    def _asset(context: dg.AssetExecutionContext):
        dbt = DbtCliResource(project_dir=dbt_project)
        args = ["seed", "--select", name]
        if context.op_config.get("full_refresh"):
            args.append("--full-refresh")
        dbt.cli(args).wait()

    return _asset


_previous: dg.AssetKey | None = None
for name in SEEDS:
    globals()[name] = _seed_asset(name, deps=[_previous] if _previous else None)
    _previous = dg.AssetKey(name)
