# Project 1

## Prepare enviroment for Data ingestion and Data Tranformation

1. Create the Virtual Environment using uv
In your terminal (/home/maxantipev/analytics-engineering/)

```
uv venv .venv
source .venv/bin/activate
```

2. Install Packages Separately using uv

```
uv pip install --upgrade pip

uv pip install dagster
    # The core data orchestrator framework used to define, schedule, and monitor your pipelines (assets, jobs, and execution graphs)

uv pip install dagster-webserver
    # Provides the local UI dashboard (dagster dev) so you can visually inspect assets, run manual triggers, and view logs

uv pip install dbt-core
    # The standard transformation engine that compiles and executes your SQL models using analytics engineering best practices (latest stable compatible version)

uv pip install dbt-duckdb
    # The database adapter plugin allowing dbt to connect and run transformations directly inside your local DuckDB database file

uv pip install dagster-dbt
    # The integration library that bridges Dagster and dbt, automatically turning your dbt models into native Dagster assets.

uv pip install requests
    # A lightweight HTTP library used to fetch raw JSON data from the public XKCD web endpoints

uv pip install pandas
    # A data manipulation library to help parse, clean, and structure tabular payloads before they land in DuckDB

uv pip install duckdb
    # The fast, embedded analytical database used to execute local SQL queries and store versioned tables

```

3. Save Your Dependencies (requirements.txt)
Save your environment state:

```
uv pip freeze > requirements.txt
```

4. Confirm version ofr DBT you need

```
dbt --version
```


## Preapre repository for Data Ingestion and Data transformation (dbt)


### Design the folder structure

```
analytics-engineering/
├── .venv/                      # Python virtual environment (uv)
├── requirements.txt            # Locked dependencies
├── ingestion/                  # 1. DATA INGESTION (Dagster & Python scripts)
│   ├── xkcd_dagster/           # Dagster orchestration project
│   │   ├── assets/             # Python scripts fetching XKCD API JSON
│   │   └── definitions.py      # Dagster entry point
│   └── data/                   # Local DuckDB database file storage
└── transformation_dbt/         # 2. DATA TRANSFORMATION (dbt project)
    ├── models/
    │   ├── staging/            # Initial cleaning of ingested tables
    │   └── marts/              # Business intelligence & trend models (PDP)
    ├── dbt_project.yml
    └── profiles.yml            # DuckDB connection profile
```

### Create the Ingestion Folder Structure

Run these commands in your terminal from your root directory

My example: (/home/maxantipev/analytics-engineering/)

```
mkdir -p ingestion
cd ingestion
```

### Initialize the Dagster project
Run the official setup command using uvx
Source: https://docs.dagster.io/getting-started/quickstart

```
uvx create-dagster@latest project xkcd_dagster
```
Respond y to the prompt to run uv sync after.

### Change to the "project_name" directory and activate enviroment

```
cd xkcd_dagster
source .venv/bin/activate

```

### Install the required dependencies in the virtual environment

```
uv add pandas requests
uv add duckdb
```
Final structure is expected this:

```
ingestion/
│   └── xkcd_dagster/
│       ├── .dg/
│       ├── .venv/
│       ├── src/
│       ├── tests/
│       ├── .gitignore
│       ├── pyproject.toml
│       ├── README.md
│       └── uv.lock
```


### Create an assets file

Software-defined assets are the primary building blocks in Dagster.
They represent the underlying entities in our pipelines, such as database tables, machine learning models, or AI processes. Together, these assets form the data platform.

Source: https://docs.dagster.io/dagster-basics-tutorial/assets


When building assets, the first step is to scaffold an assets file with the `dg` scaffold command:

```
dg scaffold defs dagster.asset assets.py
```

Creating a component at
```
<YOUR PATH>/dagster-tutorial/src/dagster_tutorial/defs/assets.py.
```

Example:
```
/home/maxantipev/analytics-engineering/ingestion/xkcd_dagster/src/xkcd_dagster/defs/assets.py.
```

This adds a file called assets.py to the dagster-tutorial module, which will contain your asset code. Using `dg` to create the file ensures it is placed where Dagster can automatically discover it:

```
src
└── dagster_tutorial
    └── defs
        └── assets.py
```

My example:

```
src
└── xkcd_dagster
    └── defs
        └── assets.py
```


### Add data
As per official documentation, next is to create a `sample_data.csv` file. This file will act as the data source for your Dagster pipeline:

```
mkdir src/dagster_quickstart/defs/data && touch src/dagster_quickstart/defs/data/sample_data.csv
```

My Example:
In this particular case we extract data from https://xkcd.com/info.0.json, where "0" can be different comic.

```
mkdir -p src/xkcd_dagster/defs/data

```
create empty file

```
touch src/xkcd_dagster/defs/data/sample_data.csv
```


```
cp src/xkcd_dagster/defs/assets.py src/xkcd_dagster/defs/step_1_ingestion.py
```

### Define the asset
As per official documentation,to define the assets for the ETL pipeline, you need to open src/dagster_quickstart/defs/assets.py file in your preferred editor and update the code.

My Example:
In this particular case we

1. create copy of existed files and rename it

```
cp src/xkcd_dagster/defs/assets.py src/xkcd_dagster/defs/step_1_ingestion.py

touch src/xkcd_dagster/defs/data/test_ingestion.ipynb
```
Python notebook adde for testing purposes

2. add import statements:

```
import dagster as dg
import pandas as pd
import requests

```

3. Explore data using this example in notebook:

```
# 1. Fetch live data from the official XKCD API endpoint
url = "https://xkcd.com/info.0.json"
response = requests.get(url)
comic_dict = response.json()

# 2. Load the JSON dictionary into a Pandas DataFrame
df = pd.DataFrame([comic_dict])

# 3. Print the schema (column names and data types)
print("--- SCHEMA & DATA TYPES ---")
display(df.dtypes)

# 4. Print the actual data preview
print("\n--- DATA PREVIEW ---")
display(df)
```

4. create shema configuration file:
schema_config_v1.json
V1 - version of schema

```
{
  "table_name": "raw_comics",
  "columns": {
    "month": "object",
    "num": "int64",
    "link": "object",
    "year": "object",
    "news": "object",
    "safe_title": "object",
    "transcript": "object",
    "alt": "object",
    "img": "object",
    "title": "object",
    "day": "object"
  }
}
```
schema_config_v2.json
V2 - version of schema, if at some point your ingestion failed due to schema drift


5. Add data processing Python functions to
- test_ingestion.ipynb
- step_1_ingestion.py

Test them

6. At this point, you can list the Dagster definitions in your project with dg list defs. You should see the asset you just created:

```
dg list defs
```

Results:
(xkcd-dagster) root@MSI:/home/maxantipev/analytics-engineering/ingestion/xkcd_dagster# dg list defs

| Section | Key              | Group   | Deps | Kinds | Description |
|---------|------------------|---------|------|-------|-------------|
| Assets  | step_1_ingestion | default |      |       |             |


7. You can also load and validate your Dagster definitions with dg check defs:
```
dg check defs
```
Result:
```
(xkcd-dagster) root@MSI:/home/maxantipev/analytics-engineering/ingestion/xkcd_dagster# dg check defs
All component YAML validated successfully.
All definitions loaded successfully.
```

8. Add schedule

Create new file: src/<project_name>/defs/schedules.py
Source: https://docs.dagster.io/guides/automate/schedules/defining-schedules

```
cd /home/maxantipev/analytics-engineering/ingestion/xkcd_dagster
dg scaffold defs dagster.schedule schedules.py

```

Add this code:
```
import dagster as dg


@dg.schedule(cron_schedule="0 8 * * 1,3,5", target="*")
def schedules(context: dg.ScheduleEvaluationContext) -> dg.RunRequest | dg.SkipReason:
    context.log.info("Evaluating XKCD schedule: checking for new comic updates...")
    return dg.RunRequest()
```

### Run your pipeline
In the terminal, navigate to your project's root directory and run:
```
dg dev
```

Open your web browser and navigate to http://localhost:3000, where you should see the Dagster UI:

Dagster UI overview: http://127.0.0.1:3000/overview/activity/timeline?groupBy=automation


In the top navigation, click the Assets tab, then click View lineage:

How to run it:
1. Click the checkbox next to step_1_ingestion.
2. Click the "Materialize selected" button near the top right.
3. Watch the run kick off to fetch your XKCD data and create your local DuckDB database!


You can also run the pipeline by using the dg launch --assets command and passing an asset selection:

```
dg launch --assets "*"
```

### Verify the results
Veryfy if data in database

```
python -c "import duckdb; print(duckdb.connect('src/xkcd_dagster/defs/data/xkcd.duckdb').execute('SELECT * FROM raw_comics_v2').fetchdf())"
```
or create SQL file:

```
SELECT * FROM xkcd.raw_comics_v2 WHERE num = 277;
```

### Commit to github

```
cd /home/maxantipev/analytics-engineering/
git status
git status --ignored
du -sh ingestion/xkcd_dagster/src/xkcd_dagster/defs/data/xkcd.duckdb
find . -name ".gitignore"
echo ".tmp_dagster_home_*" >> ingestion/xkcd_dagster/.gitignore
git add .
git commit -m "ingestion"

```


## Preapre repository for Data transformation (dbt)

## Preapre for Data Ingestion
