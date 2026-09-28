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
    │   ├── intermediate/       # Adding JOINs and Business logic to tables
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

Test them.

-- Do not fogret target schem specification:

My example:
```
 # Create ingest schema if missing & prefix table name
    con.execute("CREATE SCHEMA IF NOT EXISTS ingest;")
    target_table = f"ingest.raw_comics_{active_schema_version}"
```

6. At this point, you can list the Dagster definitions in your project with dg list defs. You should see the asset you just created:

```
cd /home/maxantipev/analytics-engineering/ingestion/xkcd_dagster
dg list defs
```

Results:
(xkcd-dagster) root@MSI:/home/maxantipev/analytics-engineering/ingestion/xkcd_dagster# dg list defs
┏━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Section   ┃ Definitions                                                 ┃
┡━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Assets    │ ┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━┓ │
│           │ ┃ Key              ┃ Group   ┃ Deps ┃ Kinds ┃ Description ┃ │
│           │ ┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━┩ │
│           │ │ step_1_ingestion │ default │      │       │             │ │
│           │ └──────────────────┴─────────┴──────┴───────┴─────────────┘ │
│ Schedules │ ┏━━━━━━━━━━━┳━━━━━━━━━━━━━━━┓                               │
│           │ ┃ Key       ┃ Cron          ┃                               │
│           │ ┡━━━━━━━━━━━╇━━━━━━━━━━━━━━━┩                               │
│           │ │ schedules │ 0 8 * * 1,3,5 │                               │
│           │ └───────────┴───────────────┘                               │
└───────────┴─────────────────────────────────────────────────────────────┘


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

### Performance: faster ingestion (parallel fetching + batching)

Each comic is one HTTP request (~0.2–0.3 s), and there are ~3,300 of them, so
fetching them one-by-one took ~30 minutes. Two small changes speed this up a lot:

- **Fetch in parallel** using Python's `ThreadPoolExecutor` (20 workers). The
  `requests.get` calls now overlap, so the download phase drops to ~1–2 minutes.
- **Write in batches of 500** (was 100). Fewer trips to DuckDB, same data.

`batch_size` and `max_workers` are set near the top of `step_1_ingestion()`
so they are easy to tune.

### Verify the results
Verify if data is in the database, in the **`ingest`** schema (table `ingest.raw_comics_v2`).

Run these from `ingestion/xkcd_dagster/`:


- 1. Quick dump (only works AFTER you re-run the asset; ingest.raw_comics_v2 doesn't exist yet)
```
python -c "import duckdb; print(duckdb.connect('/home/maxantipev/analytics-engineering/ingestion/xkcd_dagster/src/xkcd_dagster/defs/data/xkcd.duckdb', read_only=True).execute('SELECT * FROM ingest.raw_comics_v2').fetchdf())"
```

- 2. Confirm which schema the table is actually in (works NOW)
 now -> [('xkcd', 'main', 'raw_comics_v2')] ; after re-run -> [('xkcd', 'ingest', 'raw_comics_v2')]

```
python -c "import duckdb; con = duckdb.connect('/home/maxantipev/analytics-engineering/ingestion/xkcd_dagster/src/xkcd_dagster/defs/data/xkcd.duckdb', read_only=True); print(con.execute(\"SELECT table_catalog, table_schema, table_name FROM information_schema.tables WHERE table_name = 'raw_comics_v2'\").fetchall())"

```

- 3. Row count + one known comic (works AFTER re-run)

```
python -c "import duckdb; con = duckdb.connect('/home/maxantipev/analytics-engineering/ingestion/xkcd_dagster/src/xkcd_dagster/defs/data/xkcd.duckdb', read_only=True); print('rows:', con.execute('SELECT count(*) FROM ingest.raw_comics_v2').fetchone()[0]); print(con.execute('SELECT num, title FROM ingest.raw_comics_v2 WHERE num = 277').fetchall())"

```
- 4. Offline check that insert_comic_to_duckdb writes to the 'ingest' schema (works NOW, no network/DB-file)

```
python -c "
import duckdb, pandas as pd, importlib.util
spec = importlib.util.spec_from_file_location('s1', '/home/maxantipev/analytics-engineering/ingestion/xkcd_dagster/src/xkcd_dagster/defs/step_1_ingestion.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
con = duckdb.connect()
df = pd.DataFrame([{'alt':'x','day':'1','extra_parts':None,'img':'i','link':'l','month':'1','news':None,'num':1,'safe_title':'s','title':'t','transcript':'tr','year':'2006'}])
m.insert_comic_to_duckdb(con, df, schema_version='v2', target_schema='ingest')
print(con.execute(\"SELECT table_schema, table_name FROM information_schema.tables WHERE table_name = 'raw_comics_v2'\").fetchall())
print('rows:', con.execute('SELECT count(*) FROM ingest.raw_comics_v2').fetchone()[0])
"

```


or create SQL file:

```
SELECT * FROM ingest.raw_comics_v2 WHERE num = 277;


```

- 5. If it is necessary to remove specific schema

```
/home/maxantipev/analytics-engineering/.venv/bin/python -c "import duckdb; con = duckdb.connect('/home/maxantipev/analytics-engineering/ingestion/xkcd_dagster/src/xkcd_dagster/defs/data/xkcd.duckdb'); con.execute('DROP TABLE IF EXISTS main.raw_comics_v2;'); con.close(); print('Successfully deleted main.raw_comics_v2')"
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

### Create the Transfromation Folder Structure

Run these commands in your terminal from your root directory

My example: (/home/maxantipev/analytics-engineering/)

```
mkdir -p transformation_dbt
cd transformation_dbt
dbt --version
```
My example:
dbt-fusion 2.0.0-preview.164
(dbt v2 is a next-generation, Rust-based engine that powers dbt development across the platform and local tooling)

Source: https://docs.getdbt.com/guides/dbt?step=1

### Install the dbt VS Code extension
The dbt VS Code extension is available in the Visual Studio extension marketplace
https://marketplace.visualstudio.com/items?itemName=dbtLabsInc.dbt

Source: https://docs.getdbt.com/guides/dbt?step=3

### Initialize the Jaffle Shop project
Run dbt init in your terminal from the directory where you want to create the project. The dbt init command creates an example project and walks you through setting up a connection profile.

Run the official setup command using uvx
Source: https://docs.getdbt.com/guides/dbt?step=4


```
dbt init
```
Answer questions to the prompt :

My Example:

"bigquey" selected, while duckdb is not shown

```
Which adapter would you like to use?: bigquery
No dbt_cloud.yml found - proceeding without cloud pre-population
Project ID: my-1-st-project-training
Dataset: transfromation_dbt
Location (e.g., us-east1, europe-west1): US
```
Run this 

```
gcloud auth application-default login
```

### Change to the "project_name" directory and activate enviroment
Change directories into your newly created project (it will be renamed later)

```
cd jaffle_shop


```

### Create Profile file

dbt platform projects don't require a profiles.yml file unless you're developing from your local machine instead of the cloud-based UI.

Source: https://docs.getdbt.com/docs/local/profiles.yml?version=2

File Location after dbt init:
root@MSI:~/.dbt/profiles.yml

To open and edit it:
```
code ~/.dbt/profiles.yml
```
To Move the file to your project directory
```
mv /root/.dbt/profiles.yml /home/maxantipev/analytics-engineering/transformation_dbt/
```
Navigate to your project folder and test that dbt can find it locally
```
cd /home/maxantipev/analytics-engineering/transformation_dbt/jaffle_shop
dbt debug --profiles-dir ..
```
(two dots is very important)

### Update Profile File with new connection
Local file: To persist data between runs, set path to a .duckdb file on your local filesystem. DuckDB creates the file automatically if it doesn't exist.

```
profiles.yml
your_profile_name:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: './my_project.duckdb'
      schema: main   # optional; defaults to main
      threads: 4     # optional
```
Source: https://docs.getdbt.com/docs/local/connect-data-platform/duckdb-setup?version=2

My example:

```
jaffle_shop:
  target: dev
  outputs:
    dev:
      type: bigquery
      threads: 16
      database: my-1-st-project-training
      schema: transfromation_dbt
      method: oauth
      location: US
      dataproc_batch: null

    duckdb_dev:
      type: duckdb
      path: '../../ingestion/xkcd_dagster/src/xkcd_dagster/defs/data/xkcd.duckdb'
      schema: main   # optional; defaults to main
      threads: 4     # optional
```
Test. Very important relative path: "../../"
```
dbt debug --profiles-dir .. --target duckdb_dev
dbt compile --profiles-dir .. --target duckdb_dev
```

### Replace Juffle shop models with Project related models and Update Profile File

1. Rename: "domain_data_products" in profiles.yml and project.yml files
2. Update __sources.yml
3. Structure models properly as per Source: https://docs.getdbt.com/best-practices/how-we-structure/1-guide-overview?version=2

```
Staging — creating our atoms, our initial modular building blocks, from source data
Intermediate — stacking layers of logic with clear and specific purposes to prepare our staging models to join into the entities we want
Marts — bringing together our modular pieces into a wide, rich vision of the entities our organization cares about
```

4. Create staging models for "comics"
Install dbt Power User, so you can generate models from sources
Or you can developm Agent skills that can also do the same
Or Create manually

--- 
---if setting to be written to VS Code ---

python3 -c '
import json, os

settings_path = os.path.expanduser("~/.vscode-server/data/Machine/settings.json")
os.makedirs(os.path.dirname(settings_path), exist_ok=True)

data = {}
if os.path.exists(settings_path):
    try:
        with open(settings_path, "r") as f:
            data = json.load(f)
    except Exception:
        pass

data.update({
    "dbt.dbtIntegration": "core",
    "python.defaultInterpreterPath": "/home/maxantipev/analytics-engineering/ingestion/xkcd_dagster/.venv/bin/python",
    "dbt.executablePath": "/home/maxantipev/.local/bin/dbt",
    "dbt.projectPath": "/home/maxantipev/analytics-engineering/transformation_dbt/domain_data_products",
    "dbt.profilesDir": "/home/maxantipev/analytics-engineering/transformation_dbt"
})

with open(settings_path, "w") as f:
    json.dump(data, f, indent=4)

print("Settings updated successfully!")
'





python3 -c '
import json, os

settings_path = os.path.expanduser("~/.vscode-server/data/Machine/settings.json")
os.makedirs(os.path.dirname(settings_path), exist_ok=True)

data = {}
if os.path.exists(settings_path):
    try:
        with open(settings_path, "r") as f:
            data = json.load(f)
    except Exception:
        pass

data.update({
    "dbt.dbtIntegration": "fusion",
    "python.defaultInterpreterPath": "/home/maxantipev/analytics-engineering/ingestion/xkcd_dagster/.venv/bin/python",
    "dbt.executablePath": "/home/maxantipev/.local/bin/dbt",
    "dbt.projectPath": "/home/maxantipev/analytics-engineering/transformation_dbt/domain_data_products",
    "dbt.profilesDir": "/home/maxantipev/analytics-engineering/transformation_dbt"
})

with open(settings_path, "w") as f:
    json.dump(data, f, indent=4)

print("Settings updated to fusion mode!")
'

---
Move profiles to different folder:
```
mv /home/maxantipev/analytics-engineering/transformation_dbt/profiles.yml /home/maxantipev/analytics-engineering/transformation_dbt/domain_data_products/profiles.yml
```

Create gitignore

```
cd /home/maxantipev/analytics-engineering/transformation_dbt/domain_data_products
echo "profiles.yml" >> /home/maxantipev/analytics-engineering/transformation_dbt/domain_data_products/.gitignore
```



5. Do 'dbt compile' for created models, update models

The basic guideline is start as simple as possible:

🔍 Start with a view. When the view gets too long to query for end users,
⚒️ Make it a table. When the table gets too long to build in your dbt Jobs,
📚 Build it incrementally. That is, layer the data on in chunks as it comes in.

Source: https://docs.getdbt.com/best-practices/materializations/1-guide-overview?version=2

Incremental 3 key things:
- a filter to select just the new or updated records
- a conditional block that wraps our filter and only applies it when we want it
- configuration that tells dbt we want to build incrementally and helps apply the conditional filter when needed

Soiurce: https://docs.getdbt.com/best-practices/materializations/4-incremental-models?version=2

6. Add macroses if necessary

Installed packages 
- dbt-core's global macros (`dbt/include/global_project/macros/utils`) 
- and the dbt-duckdb adapter (`dbt/include/duckdb/macros/utils`) — where dbt's built-in cross-database date macros live (`date_spine`, `date_trunc`, `dateadd`, `last_day`, `generate_series`). 
The real dbt features is used are Jinja macros and the `target.type` switch (https://docs.getdbt.com/docs/build/jinja-macros), which let one template emit BigQuery or DuckDB date functions. 

To compile/execute the calendar macro:

```
cd /home/maxantipev/analytics-engineering/transformation_dbt/domain_data_products
dbt run-operation calendar_macro
dbt parse --target duckdb_dev
dbt compile --select calendar --target duckdb_dev
cat target/compiled/domain_data_products/models/marts/comics/calendar.sql
sed -n '1,40p' target/compiled/domain_data_products/models/marts/comics/calendar.sql
```

6. Add yml files 

7. Check, validate

The `dbt parse` command parses your dbt project files, validates their syntax, checks for structural errors, and builds a manifest of your project (storing it in the target/manifest.json file), without compiling or executing any SQL models against your database.
`dbt compile` Does everything parse does, plus evaluates all Jinja code.

My example: 
```
dbt parse --target duckdb_dev
dbt compile --target duckdb_dev
dbt run --select +models/comics --target duckdb_dev
dbt run --full-refresh --select +models/marts/comics --target duckdb_dev
dbt test --select +models/marts/comics --target duckdb_dev
```

My example (with .env - see below ".env" creation)

```
# Export Environment Variables in Your Terminal
# Because dbt CLI commands do not automatically read .env files by default, load the variables # # into your current shell session:


cd /home/maxantipev/analytics-engineering/transformation_dbt/domain_data_products
export $(cat .env | xargs)

# Verify that dbt can read the path variable:


echo $XKCD_DUCKDB_PATH

# test connection

dbt debug --target duckdb_dev

dbt run --full-refresh --select +models/comics --target duckdb_dev

dbt test --select +models/comics --target duckdb_dev



dbt seed --target duckdb_dev
dbt run --full-refresh --target duckdb_dev

dbt test --target duckdb_dev

```

8. If several models, rearrange folder structure. Check, validate

My Example:

```
Current structure is "layer-first"__ (`staging/`, `intermediate/`, `marts/` at the top, with `comics` and `jaffle_shop` nested inside each). 

Future structure to invert this to __"domain-first"__ (`comics/`, `jaffle_shop/` at the top, with `staging`/`intermediate`/`marts` nested inside each).

```

9. Verify execution

```
(xkcd-dagster) root@MSI:/home/maxantipev/analytics-engineering/transformation_dbt/domain_data_products# python3 -c "
import duckdb
con = duckdb.connect('/home/maxantipev/analytics-engineering/ingestion/xkcd_dagster/src/xkcd_dagster/defs/data/xkcd.duckdb', read_only=True)
query = '''
SELECT 'ingest.raw_comics_v2' AS table_name, count(*) AS total_rows FROM ingest.raw_comics_v2
UNION ALL
SELECT 'mart.comics' AS table_name, count(*) AS total_rows FROM mart.comics;
'''
print(con.execute(query).df())
"
             table_name  total_rows
0  ingest.raw_comics_v2        3302
1           mart.comics        3302
(xkcd-dagster) root@MSI:/home/maxantipev/analytics-engineering/transformation_dbt/domain_data_products# 
```



## Migrate from local DuckDB to MotherDuck

### Step 1. Create file .env

Place the .env file directly in your project root folder:

My Example:

```
touch /home/maxantipev/analytics-engineering/ingestion/xkcd_dagster/.env

```
Your directory layout should look like this:

Plaintext
ingestion/
└── xkcd_dagster/
    ├── .env                           
    ├── src/
    └── .venv/                         


### Step 2: Get Your MotherDuck Service Account / Token
- Log into your MotherDuck Account.
- Click on your profile icon in the top right corner and select Settings (or Service Accounts).
- Under Access Tokens, click Create Token.
- Copy the generated token string (starts with ey...).


### Step 3: Set Up Credentials Configuration File (inside env)

My Example:
```
echo 'MOTHERDUCK_TOKEN="YOUR_ACTUAL_MOTHERDUCK_TOKEN"' > /home/maxantipev/analytics-engineering/ingestion/xkcd_dagster/.env

cat /home/maxantipev/analytics-engineering/ingestion/xkcd_dagster/.env

```

Security Note: Make sure to add motherduck credentials (.env) to your .gitignore file so credentials are not committed to source control.(For local development)

```
echo ".env" >> /home/maxantipev/analytics-engineering/.gitignore
```

Add local Duckdb:

```
echo 'XKCD_DUCKDB_PATH="/home/maxantipev/analytics-engineering/ingestion/xkcd_dagster/src/xkcd_dagster/defs/data/xkcd.duckdb"' >> /home/maxantipev/analytics-engineering/ingestion/xkcd_dagster/.env
```

### Step 4: Connect via Python / Dagster

Use python-dotenv to automatically load your MOTHERDUCK_TOKEN from the .env file into Python's environment variables.

- Add import line:

```
from dotenv import load_dotenv
```

- Add execution line right after imports:

```
load_dotenv()
```

- Comment out local path line in get_duckdb_connection:

```
# db_path: str = "src/xkcd_dagster/defs/data/xkcd.duckdb", # Local DuckDB
```


- Add the MotherDuck path line in get_duckdb_connection:

```
db_path: str = "md:xkcd", # Mother Duck
```


### Step 5: Configure profiles.yml for MotherDuck in DBT
Open or edit your dbt profiles file (located at ~/.dbt/profiles.yml) and configure it with the dbt-duckdb adapter:

My Example

```
xkcd_dbt_project:
  ...
      motherduck_dev:
      type: duckdb
      path: 'md:xkcd'
      schema: staging    # <--- Default base schema
      threads: 4
      token: "{{ env_var('MOTHERDUCK_TOKEN') }}"
```

Tip: Run against MotherDuck: Specify the target flag when executing dbt:

```
dbt run --target motherduck_dev
```

### Step 6: Create link to reuse the same .env credentials

Create a symbolic link in the transformation_dbt directory pointing to the original .env

```
ln -s /home/maxantipev/analytics-engineering/ingestion/xkcd_dagster/.env /home/maxantipev/analytics-engineering/transformation_dbt/domain_data_product/.env
```



### Step 7. Test Mother Duck connection

1. Run dbt parse for MotherDuck
```
# Load environment variables (MOTHERDUCK_TOKEN) and parse project
cd /home/maxantipev/analytics-engineering/transformation_dbt/domain_data_products
export $(cat .env | xargs)
dbt parse --target motherduck_dev
```

2. Verify the Live Cloud Connection with dbt debug
While dbt parse only validates project syntax locally, dbt debug connects directly to MotherDuck in the cloud to verify your credentials, database connection, and permissions:

```
dbt debug --target motherduck_dev
```

What success looks like:
All green checks, specifically under Connection:

Plaintext
  Connection:
    type: duckdb
    path: md:xkcd
    database: xkcd
    schema: staging
    Connection test: OK connection ok

### Step 8. Create Database in MotherDuck

MotherDuck requires the database to be __created__ before you can attach to it.

__Option A — via the MotherDuck UI:__

1. Go to [](https://app.motherduck.com)<https://app.motherduck.com>
2. Create a new database named exactly `xkcd`.
3. Re-run the Dagster ingestion.

__Option B — one-time code :__

```

python3 -c '
import duckdb
from dotenv import dotenv_values

cfg = dotenv_values("/home/maxantipev/analytics-engineering/ingestion/xkcd_dagster/.env")
tok = cfg["MOTHERDUCK_TOKEN"]

con = duckdb.connect("md:", config={"motherduck_token": tok})
con.execute("CREATE DATABASE IF NOT EXISTS xkcd")
print(con.execute("SHOW DATABASES").fetchall())
con.close()
'

```



























You can read the token directly from your JSON credentials file (or environment variable) and pass it into the DuckDB connection string.
Python Code Snippet



Python
import json
import duckdb


def get_duckdb_connection(
    config_path: str = "motherduck_credentials.json",
):
  """Reads MotherDuck credentials from JSON and establishes a connection."""
  # Load token and database from JSON file
  with open(config_path, "r") as f:
    creds = json.load(f)

  token = creds["motherduck_token"]
  database = creds.get("database", "xkcd")

  # Pass token directly into MotherDuck connection string
  con = duckdb.connect(f"md:{database}?motherduck_token={token}")
  return con


Alternatively, if MOTHERDUCK_TOKEN is exported in your environment variables (export MOTHERDUCK_TOKEN="your_token"), DuckDB detects it automatically when running duckdb.connect("md:xkcd").
Step 4: Configure profiles.yml for dbt
To test your dbt transformations against MotherDuck using the dbt-duckdb adapter, configure your ~/.dbt/profiles.yml file as follows:



YAML
xkcd_dbt_project:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: 'md:xkcd'
      # MotherDuck token passed via environment variable or inline string
      token: "{{ env_var('MOTHERDUCK_TOKEN') }}"

