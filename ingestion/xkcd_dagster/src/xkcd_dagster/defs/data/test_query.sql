SHOW SCHEMAS;

SELECT schema_name 
FROM information_schema.schemata 
WHERE catalog_name = 'xkcd' 
  AND schema_name NOT IN ('main', 'information_schema', 'pg_catalog')
ORDER BY schema_name;

SELECT 
* 
FROM 
"xkcd"."ingest"."raw_comics_v2"
WHERE num = 277;

SELECT 
    table_catalog,
    table_schema,
    table_name,
    table_type
FROM information_schema.tables;

SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'raw_comics_v2';

SELECT * FROM "xkcd"."ingest"."raw_comics_v2" WHERE num = 277;
SELECT * FROM "xkcd"."ingest"."raw_comics_v2" WHERE num = 1017;
SELECT * FROM "xkcd"."ingest"."raw_comics_v2" WHERE num = 2067;

SELECT * 
FROM  "xkcd"."ingest"."comics"
WHERE is_valid_date IS NOT TRUE;

DROP TABLE IF EXISTS main.raw_comics_v2;
DROP SCHEMA IF EXISTS bronze CASCADE;
DROP SCHEMA IF EXISTS silver CASCADE;
DROP SCHEMA IF EXISTS xkcd CASCADE;

SELECT * FROM "xkcd"."mart"."comics";



DROP VIEW IF EXISTS bronze.stg_comics;
DROP TABLE IF EXISTS bronze.stg_comics;
DROP SCHEMA IF EXISTS bronze CASCADE;

DROP VIEW IF EXISTS "Bronze".stg_comics;
DROP TABLE IF EXISTS "Bronze".stg_comics;
DROP SCHEMA IF EXISTS "Bronze" CASCADE;

SELECT * FROM bronze.stg_comics;


SELECT 
    table_schema,
    table_name,
    table_type
FROM information_schema.tables
WHERE table_catalog = 'xkcd'
ORDER BY table_schema, table_name;

SELECT 
    schema_name,
    table_name,
    column_count,
    estimated_size AS estimated_rows
FROM duckdb_tables()
ORDER BY schema_name, table_name;


SELECT 
    table_schema,
    table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_catalog = 'xkcd'
  AND table_schema NOT IN ('information_schema', 'pg_catalog')
ORDER BY table_schema, table_name, ordinal_position;