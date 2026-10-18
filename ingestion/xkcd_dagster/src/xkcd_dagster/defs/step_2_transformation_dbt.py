import dagster as dg
from xkcd_dagster.defs.pipeline_config import INGESTION_KEYS_BY_GROUP
from xkcd_dagster.defs.transformation_dbt.template_vars import MODELS_DIR, group_from_fqn

# 2. Instantiate extractor
extractor = group_from_fqn()

# 3. Extract groups dynamically from subfolders
all_groups = [
    extractor([MODELS_DIR.parent.name, folder.name])
    for folder in MODELS_DIR.iterdir()
    if folder.is_dir()
]

# 4. Instantiate ingestion and transformation jobs for Dagster discovery
for group in all_groups:
    ingestion = dg.AssetSelection.assets(*INGESTION_KEYS_BY_GROUP[group])
    transformation = dg.AssetSelection.groups(group) - ingestion

    globals()[f"{group}_ingestion_job"] = dg.define_asset_job(
        name=f"{group}_ingestion_job",
        selection=ingestion,
    )

    globals()[f"{group}_transformation_job"] = dg.define_asset_job(
        name=f"{group}_transformation_job",
        selection=transformation,
    )
