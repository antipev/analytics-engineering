{{ config(
    materialized='view',
    schema='staging'
) }}

WITH

source AS (

    
    SELECT 
      * 
    FROM {{ source('xkcd_duckdb', 'raw_comics_v2') }}

),

dedup AS (

    SELECT 
      *
    FROM source
    QUALIFY ROW_NUMBER() OVER (
    PARTITION BY num) = 1
    
)


SELECT
  * 
FROM dedup
