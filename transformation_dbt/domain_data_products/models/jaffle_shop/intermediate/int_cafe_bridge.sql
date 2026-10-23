{{ config(materialized='view', schema='intermediate') }}


-- Unified Star Schema bridge for the jaffle_shop data product.
--
-- Grain: one row per record per reporting table, identified by `stage`.
-- Each row fills its own key plus the keys of the tables it can be joined to.
-- Every other key column is NULL, so a bridge row never claims a record that
-- belongs to a different table.
--
-- Never add a join to this model. Consumers join each reporting table to its own
-- _key_ column; that is what keeps the join path single and fan-out free.
--
-- Key contract per stage (● = populated, · = NULL):
--
--   stage              customers  locations  orders  order_items  products  supplies
--   cafe_customers         ●          ·         ·         ·           ·         ·
--   cafe_locations         ·          ●         ·         ·           ·         ·
--   cafe_orders            ●          ●         ●         ·           ·         ·
--   cafe_order_items       ●          ●         ●         ●           ●         ·
--   cafe_products          ·          ·         ·         ·           ●         ·
--   cafe_supplies          ·          ·         ·         ·           ●         ●

WITH

unioned AS (

    SELECT
        'cafe_customers' AS stage,

        _key_cafe_customers,
        CAST(NULL AS varchar) AS _key_cafe_locations,
        CAST(NULL AS varchar) AS _key_cafe_orders,
        CAST(NULL AS varchar) AS _key_cafe_order_items,
        CAST(NULL AS varchar) AS _key_cafe_products,
        CAST(NULL AS varchar) AS _key_cafe_supplies

    FROM {{ ref('int_cafe_customers') }}

    UNION ALL

    SELECT
        'cafe_locations' AS stage,

        CAST(NULL AS varchar) AS _key_cafe_customers,
        _key_cafe_locations,
        CAST(NULL AS varchar) AS _key_cafe_orders,
        CAST(NULL AS varchar) AS _key_cafe_order_items,
        CAST(NULL AS varchar) AS _key_cafe_products,
        CAST(NULL AS varchar) AS _key_cafe_supplies

    FROM {{ ref('int_cafe_locations') }}

    UNION ALL

    SELECT
        'cafe_orders' AS stage,

        _key_cafe_customers,
        _key_cafe_locations,
        _key_cafe_orders,
        CAST(NULL AS varchar) AS _key_cafe_order_items,
        CAST(NULL AS varchar) AS _key_cafe_products,
        CAST(NULL AS varchar) AS _key_cafe_supplies

    FROM {{ ref('int_cafe_orders') }}

    UNION ALL

    SELECT
        'cafe_order_items' AS stage,

        _key_cafe_customers,
        _key_cafe_locations,
        _key_cafe_orders,
        _key_cafe_order_items,
        _key_cafe_products,
        CAST(NULL AS varchar) AS _key_cafe_supplies

    FROM {{ ref('int_cafe_order_items') }}

    UNION ALL

    SELECT
        'cafe_products' AS stage,

        CAST(NULL AS varchar) AS _key_cafe_customers,
        CAST(NULL AS varchar) AS _key_cafe_locations,
        CAST(NULL AS varchar) AS _key_cafe_orders,
        CAST(NULL AS varchar) AS _key_cafe_order_items,
        _key_cafe_products,
        CAST(NULL AS varchar) AS _key_cafe_supplies

    FROM {{ ref('int_cafe_products') }}

    UNION ALL

    SELECT
        'cafe_supplies' AS stage,

        CAST(NULL AS varchar) AS _key_cafe_customers,
        CAST(NULL AS varchar) AS _key_cafe_locations,
        CAST(NULL AS varchar) AS _key_cafe_orders,
        CAST(NULL AS varchar) AS _key_cafe_order_items,
        _key_cafe_products,
        _key_cafe_supplies

    FROM {{ ref('int_cafe_supplies') }}

)

SELECT * FROM unioned
