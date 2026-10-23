{{ config(materialized='view', schema='intermediate') }}

-- Unified Star Schema key layer for jaffle_shop.
-- Thin view over staging: staging grain, staging columns, key added.
-- Sits upstream of marts.cafe_customers, which enriches it with lifetime metrics.

WITH customers AS (
    SELECT * FROM {{ ref('stg_cafe_customers') }}
)

SELECT
    customers.*,
    ---------- unified star schema key
    customers.customer_id AS _key_cafe_customers
FROM customers
