# Analytics Engineering — XKCD and Jaffle Shop

Two domains, one warehouse: Dagster orchestrates XKCD ingestion and six Jaffle Shop seed loads into MotherDuck, dbt builds and tests the models, Malloy defines the semantic layer, and Credible and Publisher expose it to people and agents. Nothing runs while idle; Cloud Scheduler wakes a scale-to-zero Cloud Run service once a month.

[![Analytics engineering architecture, version 5](PICTURES/analytics-architecture-v5.svg)](PICTURES/analytics-architecture-v5.svg)

*Architecture, version 5 — sources → ingest → land → transform → isolate domains → define semantics → explore. Click the diagram to open it at full size.*

Open the diagram at full size, then start at **[PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md)** for the architecture, orchestration, CI/CD and validation evidence, or **[REPOSITORY_MAP.md](REPOSITORY_MAP.md)** for the file-by-file inventory.
