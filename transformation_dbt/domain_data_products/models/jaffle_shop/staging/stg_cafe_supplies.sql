{{ config(materialized='view', schema='staging') }}


WITH

source AS (

    -- {# This references seed (CSV) data - try switching to {{ source('ecom', 'raw_supplies') }} #}
    SELECT * FROM {{ source('ecom', 'raw_supplies') }}

),

renamed AS (

    SELECT

        ----------  ids
        {{ dbt_utils.generate_surrogate_key(['id', 'sku']) }} AS supply_uuid,
        id AS supply_id,
        sku AS product_id,

        ---------- text
        name AS supply_name,

        ---------- numerics
        {{ cents_to_dollars('cost') }} AS supply_cost,

        ---------- booleans
        perishable AS is_perishable_supply

    FROM source

)

SELECT * FROM renamed
