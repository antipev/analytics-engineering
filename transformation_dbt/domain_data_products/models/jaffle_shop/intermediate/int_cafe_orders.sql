{{ config(materialized='view', schema='intermediate') }}

-- Unified Star Schema key layer for jaffle_shop.
-- stg_cafe_orders already exposes customer_id and location_id, so the ancestor
-- keys come straight from staging - no join needed.

WITH orders AS (
    SELECT * FROM {{ ref('stg_cafe_orders') }}
)

SELECT
    orders.*,
    ---------- unified star schema keys
    orders.order_id      AS _key_cafe_orders,
    orders.customer_id   AS _key_cafe_customers,
    orders.location_id   AS _key_cafe_locations
FROM orders
