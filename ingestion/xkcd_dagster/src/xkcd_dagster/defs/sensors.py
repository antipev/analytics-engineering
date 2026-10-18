import dagster as dg


@dg.asset_sensor(
    asset_key=dg.AssetKey("raw_comics_v2"),
    job_name="comics_transformation_job",
    name="comics_transformation_after_ingestion",
    minimum_interval_seconds=15,
    default_status=dg.DefaultSensorStatus.RUNNING,
)
def comics_transformation_after_ingestion(context: dg.SensorEvaluationContext):
    context.log.info("raw_comics_v2 materialized; launching comics_transformation_job")
    return dg.RunRequest(tags={"triggered_by": "raw_comics_v2"})


@dg.asset_sensor(
    asset_key=dg.AssetKey("raw_supplies"),  # last seed in the dependency chain
    job_name="jaffle_shop_transformation_job",
    name="jaffle_shop_transformation_after_ingestion",
    minimum_interval_seconds=15,
    default_status=dg.DefaultSensorStatus.RUNNING,
)
def jaffle_shop_transformation_after_ingestion(context: dg.SensorEvaluationContext):
    context.log.info("raw_supplies materialized; launching jaffle_shop_transformation_job")
    return dg.RunRequest(tags={"triggered_by": "raw_supplies"})
