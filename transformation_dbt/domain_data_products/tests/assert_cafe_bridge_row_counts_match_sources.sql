-- Fails when the bridge does not contain exactly one row per source record.
-- Counts are read from the marts, so this proves both that the key views are
-- row-preserving and that the bridge mirrors them.

WITH source_counts AS (

    SELECT 'cafe_customers'   AS stage, COUNT(*) AS row_count FROM {{ ref('cafe_customers') }}
    UNION ALL
    SELECT 'cafe_locations'   AS stage, COUNT(*) AS row_count FROM {{ ref('cafe_locations') }}
    UNION ALL
    SELECT 'cafe_orders'      AS stage, COUNT(*) AS row_count FROM {{ ref('cafe_orders') }}
    UNION ALL
    SELECT 'cafe_order_items' AS stage, COUNT(*) AS row_count FROM {{ ref('cafe_order_items') }}
    UNION ALL
    SELECT 'cafe_products'    AS stage, COUNT(*) AS row_count FROM {{ ref('cafe_products') }}
    UNION ALL
    SELECT 'cafe_supplies'    AS stage, COUNT(*) AS row_count FROM {{ ref('cafe_supplies') }}

),

bridge_counts AS (

    SELECT stage, COUNT(*) AS row_count
    FROM {{ ref('cafe_bridge') }}
    GROUP BY 1

)

SELECT
    COALESCE(source_counts.stage, bridge_counts.stage) AS stage,
    source_counts.row_count AS source_row_count,
    bridge_counts.row_count AS bridge_row_count

FROM source_counts

FULL OUTER JOIN bridge_counts ON source_counts.stage = bridge_counts.stage

WHERE COALESCE(source_counts.row_count, -1) <> COALESCE(bridge_counts.row_count, -1)
