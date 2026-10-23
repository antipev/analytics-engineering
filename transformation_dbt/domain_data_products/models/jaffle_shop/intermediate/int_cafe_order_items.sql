{{ config(materialized='view', schema='intermediate') }}

-- Unified Star Schema key layer for jaffle_shop.
-- stg_cafe_order_items exposes order_item_id, order_id and product_id, but not
-- customer_id or location_id. stg_cafe_orders is one row per order_id, so this
-- join cannot change the item grain; it only brings the two ancestor keys down.

WITH order_items AS (
    SELECT * FROM {{ ref('stg_cafe_order_items') }}
),

orders AS (
    SELECT order_id, customer_id, location_id FROM {{ ref('stg_cafe_orders') }}
)

SELECT
    order_items.*,
    ---------- unified star schema keys
    order_items.order_item_id AS _key_cafe_order_items,
    order_items.order_id      AS _key_cafe_orders,
    order_items.product_id    AS _key_cafe_products,
    orders.customer_id        AS _key_cafe_customers,
    orders.location_id        AS _key_cafe_locations
FROM order_items

LEFT JOIN orders ON order_items.order_id = orders.order_id
