-- Fails when a bridge row fills a key its stage must leave NULL, or leaves
-- empty a key its stage must fill. Contract: docs §2.2.

WITH expected AS (

    SELECT * FROM (
        VALUES
            ('cafe_customers',   TRUE,  FALSE, FALSE, FALSE, FALSE, FALSE),
            ('cafe_locations',   FALSE, TRUE,  FALSE, FALSE, FALSE, FALSE),
            ('cafe_orders',      TRUE,  TRUE,  TRUE,  FALSE, FALSE, FALSE),
            ('cafe_order_items', TRUE,  TRUE,  TRUE,  TRUE,  TRUE,  FALSE),
            ('cafe_products',    FALSE, FALSE, FALSE, FALSE, TRUE,  FALSE),
            ('cafe_supplies',    FALSE, FALSE, FALSE, FALSE, TRUE,  TRUE)
    ) AS t (
        stage,
        has_customers,
        has_locations,
        has_orders,
        has_order_items,
        has_products,
        has_supplies
    )

),

actual AS (

    SELECT
        stage,

        _key_cafe_customers   IS NOT NULL AS has_customers,
        _key_cafe_locations   IS NOT NULL AS has_locations,
        _key_cafe_orders      IS NOT NULL AS has_orders,
        _key_cafe_order_items IS NOT NULL AS has_order_items,
        _key_cafe_products    IS NOT NULL AS has_products,
        _key_cafe_supplies    IS NOT NULL AS has_supplies

    FROM {{ ref('cafe_bridge') }}

)

SELECT
    actual.stage,
    actual.has_customers,
    actual.has_locations,
    actual.has_orders,
    actual.has_order_items,
    actual.has_products,
    actual.has_supplies,
    expected.has_customers   AS expected_has_customers,
    expected.has_locations   AS expected_has_locations,
    expected.has_orders      AS expected_has_orders,
    expected.has_order_items AS expected_has_order_items,
    expected.has_products    AS expected_has_products,
    expected.has_supplies    AS expected_has_supplies

FROM actual

LEFT JOIN expected ON actual.stage = expected.stage

WHERE expected.stage IS NULL
   OR actual.has_customers   <> expected.has_customers
   OR actual.has_locations   <> expected.has_locations
   OR actual.has_orders      <> expected.has_orders
   OR actual.has_order_items <> expected.has_order_items
   OR actual.has_products    <> expected.has_products
   OR actual.has_supplies    <> expected.has_supplies
