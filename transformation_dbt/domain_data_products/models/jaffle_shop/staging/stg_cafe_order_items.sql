{{ config(materialized='view', schema='staging') }}


WITH

source AS (

    -- {# This references seed (CSV) data - try switching to {{ source('ecom', 'raw_items') }} #}
    SELECT * FROM {{ source('ecom', 'raw_items') }}

),

renamed AS (

    SELECT

        ----------  ids
        id AS order_item_id,
        order_id,
        sku AS product_id

    FROM source

)

SELECT * FROM renamed
