import os
import dagster as dg


@dg.schedule(
    cron_schedule=os.getenv("DAGSTER_CRON_SCHEDULE", os.getenv("CRON_SCHEDULE", "0 8 1 * *")),
    job_name="comics_ingestion_job",
    name="comics_ingestion_schedule",
    default_status=dg.DefaultScheduleStatus.STOPPED,
)
def comics_ingestion_schedule(context: dg.ScheduleEvaluationContext):
    context.log.info("Launching comics_ingestion_job; transformation is sensor-triggered.")
    return dg.RunRequest(
        tags={"domain": "comics", "stage": "ingestion"},
    )


