{{ config(materialized='view', schema='staging') }}


WITH

source AS (

    -- {# This references seed (CSV) data - try switching to {{ source('ecom', 'raw_orders') }} #}
    SELECT * FROM {{ source('ecom', 'raw_orders') }}

),

renamed AS (

    SELECT

        ----------  ids
        id AS order_id,
        store_id AS location_id,
        customer AS customer_id,

        ---------- numerics
        subtotal AS subtotal_cents,
        tax_paid AS tax_paid_cents,
        order_total AS order_total_cents,
        {{ cents_to_dollars('subtotal') }} AS subtotal,
        {{ cents_to_dollars('tax_paid') }} AS tax_paid,
        {{ cents_to_dollars('order_total') }} AS order_total,

        ---------- timestamps
        CAST(ordered_at AS date) AS order_date

    FROM source

)

SELECT * FROM renamed
