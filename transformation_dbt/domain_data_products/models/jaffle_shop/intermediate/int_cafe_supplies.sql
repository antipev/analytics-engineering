{{ config(materialized='view', schema='intermediate') }}

-- Unified Star Schema key layer for jaffle_shop.
-- supply_uuid is already a composite key from stg_cafe_supplies; expose it as-is.
-- product_id links to cafe_products and is carried as a foreign key.

WITH supplies AS (
    SELECT * FROM {{ ref('stg_cafe_supplies') }}
)

SELECT
    supplies.*,
    ---------- unified star schema keys
    supplies.supply_uuid AS _key_cafe_supplies,
    supplies.product_id  AS _key_cafe_products
FROM supplies
