import dagster as dg
from xkcd_dagster.defs.transformation_dbt.template_vars import MODELS_DIR, group_from_fqn

# 2. Instantiate extractor
extractor = group_from_fqn()

# 3. Extract groups dynamically from subfolders
all_groups = [
    extractor([MODELS_DIR.parent.name, folder.name])
    for folder in MODELS_DIR.iterdir()
    if folder.is_dir()
]

# 4. Instantiate top-level asset jobs for Dagster discovery
for group in all_groups:
    globals()[f"{group}_job"] = dg.define_asset_job(
        name=f"{group}_job", # ← the job NAME is created here, like comics_job, jaffle_shop_job 
        selection=dg.AssetSelection.groups(group),
    )