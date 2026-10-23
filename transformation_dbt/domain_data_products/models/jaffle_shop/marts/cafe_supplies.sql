{{ config(materialized='table', schema='marts') }}


WITH

supplies AS (

    SELECT * FROM {{ ref('int_cafe_supplies') }}

)

SELECT * FROM supplies
