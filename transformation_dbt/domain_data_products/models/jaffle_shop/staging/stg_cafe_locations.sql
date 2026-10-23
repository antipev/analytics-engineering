{{ config(materialized='view', schema='staging') }}


WITH

source AS (

    -- {# This references seed (CSV) data - try switching to {{ source('ecom', 'raw_stores') }} #}
    SELECT * FROM {{ source('ecom', 'raw_stores') }}

),

renamed AS (

    SELECT

        ----------  ids
        id AS location_id,

        ---------- text
        name AS location_name,

        ---------- numerics
        tax_rate,

        ---------- timestamps
        CAST(opened_at AS date) AS opened_date

    FROM source

)

SELECT * FROM renamed
