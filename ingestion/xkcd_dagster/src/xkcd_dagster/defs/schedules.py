import dagster as dg


@dg.schedule(cron_schedule="0 8 * * 1,3,5", target="*")
def schedules(context: dg.ScheduleEvaluationContext) -> dg.RunRequest | dg.SkipReason:
    context.log.info("Evaluating XKCD schedule: checking for new comic updates...")
    return dg.RunRequest()

