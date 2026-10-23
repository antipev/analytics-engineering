{{ config(materialized='view', schema='staging') }}


WITH

source AS (

    -- {# This references seed (CSV) data - try switching to {{ source('ecom', 'raw_customers') }} #}
    SELECT * FROM {{ source('ecom', 'raw_customers') }}

),

renamed AS (

    SELECT

        ----------  ids
        id AS customer_id,

        ---------- text
        name AS customer_name

    FROM source

)

SELECT * FROM renamed
