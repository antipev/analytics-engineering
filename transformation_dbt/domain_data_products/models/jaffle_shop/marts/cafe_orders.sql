{{ config(materialized='table', schema='marts') }}


WITH

orders AS (

    SELECT * FROM {{ ref('int_cafe_orders') }}

),

order_items AS (

    SELECT * FROM {{ ref('cafe_order_items') }}

),

order_items_summary AS (

    SELECT
        order_id,

        SUM(supply_cost) AS order_cost,
        SUM(product_price) AS order_items_subtotal,
        COUNT(order_item_id) AS count_order_items,

        -- Try switching these from 'sum' to 'count' and then run 'dbt test'
        SUM(
            CASE
                WHEN is_food_item THEN 1
                ELSE 0
            END
        ) AS count_food_items,
        SUM(
            CASE
                WHEN is_drink_item THEN 1
                ELSE 0
            END
        ) AS count_drink_items

    FROM order_items

    GROUP BY 1

),

compute_booleans AS (

    SELECT
        orders.*,

        order_items_summary.order_cost,
        order_items_summary.order_items_subtotal,
        order_items_summary.count_food_items,
        order_items_summary.count_drink_items,
        order_items_summary.count_order_items,
        order_items_summary.count_food_items > 0 AS is_food_order,
        order_items_summary.count_drink_items > 0 AS is_drink_order

    FROM orders

    LEFT JOIN
        order_items_summary
        ON orders.order_id = order_items_summary.order_id

),

customer_order_count AS (

    SELECT
        *,

        ROW_NUMBER() OVER (
            PARTITION BY customer_id
            ORDER BY order_date ASC
        ) AS customer_order_number

    FROM compute_booleans

)

SELECT
    customer_order_count.* EXCLUDE (
        _key_cafe_orders,
        _key_cafe_customers,
        _key_cafe_locations
    ),

    ---------- unified star schema keys (always last)
    _key_cafe_orders,
    _key_cafe_customers,
    _key_cafe_locations

FROM customer_order_count
