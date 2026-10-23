{{ config(materialized='table', schema='marts') }}


WITH

locations AS (

    SELECT * FROM {{ ref('int_cafe_locations') }}

)

SELECT * FROM locations
