{{ config(materialized='table', schema='marts') }}


WITH

products AS (

    SELECT * FROM {{ ref('int_cafe_products') }}

)

SELECT * FROM products
