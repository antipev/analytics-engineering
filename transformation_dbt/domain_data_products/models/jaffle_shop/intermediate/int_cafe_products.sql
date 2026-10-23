{{ config(materialized='view', schema='intermediate') }}

-- Unified Star Schema key layer for jaffle_shop.
-- Thin view over staging: staging grain, staging columns, key added.
-- Sits upstream of marts.cafe_products.

WITH products AS (
    SELECT * FROM {{ ref('stg_cafe_products') }}
)

SELECT
    products.*,
    ---------- unified star schema key
    products.product_id AS _key_cafe_products
FROM products
