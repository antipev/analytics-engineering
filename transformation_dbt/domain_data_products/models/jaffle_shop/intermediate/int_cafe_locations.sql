{{ config(materialized='view', schema='intermediate') }}

-- Unified Star Schema key layer for jaffle_shop.
-- Thin view over staging: staging grain, staging columns, key added.
-- Sits upstream of marts.cafe_locations.

WITH locations AS (
    SELECT * FROM {{ ref('stg_cafe_locations') }}
)

SELECT
    locations.*,
    ---------- unified star schema key
    locations.location_id AS _key_cafe_locations
FROM locations
