{{ config(materialized='table', schema='marts') }}


WITH

order_items AS (

    SELECT * FROM {{ ref('int_cafe_order_items') }}

),


orders AS (

    SELECT * FROM {{ ref('int_cafe_orders') }}

),

products AS (

    SELECT * FROM {{ ref('int_cafe_products') }}

),

supplies AS (

    SELECT * FROM {{ ref('int_cafe_supplies') }}

),

order_supplies_summary AS (

    SELECT
        product_id,

        SUM(supply_cost) AS supply_cost

    FROM supplies

    GROUP BY 1

),

joined AS (

    SELECT
        order_items.*,

        orders.order_date,

        products.product_name,
        products.product_price,
        products.is_food_item,
        products.is_drink_item,

        order_supplies_summary.supply_cost

    FROM order_items

    LEFT JOIN orders ON order_items.order_id = orders.order_id

    LEFT JOIN products ON order_items.product_id = products.product_id

    LEFT JOIN order_supplies_summary
        ON order_items.product_id = order_supplies_summary.product_id

)

SELECT
    joined.* EXCLUDE (
        _key_cafe_order_items,
        _key_cafe_orders,
        _key_cafe_products,
        _key_cafe_customers,
        _key_cafe_locations
    ),

    ---------- unified star schema keys (always last)
    _key_cafe_order_items,
    _key_cafe_orders,
    _key_cafe_products,
    _key_cafe_customers,
    _key_cafe_locations

FROM joined
