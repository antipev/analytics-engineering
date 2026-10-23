{{ config(materialized='view', schema='staging') }}


WITH

source AS (

    -- {# This references seed (CSV) data - try switching to {{ source('ecom', 'raw_products') }} #}
    SELECT * FROM {{ source('ecom', 'raw_products') }}

),

renamed AS (

    SELECT

        ----------  ids
        sku AS product_id,

        ---------- text
        name AS product_name,
        type AS product_type,
        description AS product_description,


        ---------- numerics
        {{ cents_to_dollars('price') }} AS product_price,

        ---------- booleans
        COALESCE(type = 'jaffle', FALSE) AS is_food_item,

        COALESCE(type = 'beverage', FALSE) AS is_drink_item

    FROM source

)

SELECT * FROM renamed
