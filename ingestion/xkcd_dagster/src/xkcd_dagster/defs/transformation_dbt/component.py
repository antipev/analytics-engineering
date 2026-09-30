import dagster as dg
from dagster_dbt import DbtProjectComponent


class FullRefreshDbtProjectComponent(DbtProjectComponent):
    """DbtProjectComponent with a runtime `full_refresh` toggle."""

    @property
    def op_config_schema(self) -> type[dg.Config]:
        class DbtRunConfig(dg.Config):
            full_refresh: bool = False   # dbt-standard name (snake_case)

        return DbtRunConfig

    def get_cli_args(self, context: dg.AssetExecutionContext) -> list[str]:
        args = list(super().get_cli_args(context))
        if context.op_config.get("full_refresh"):
            args.append("--full-refresh")   # -> dbt build --full-refresh
        return args
