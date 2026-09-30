{{ config(materialized='table', schema='marts') }}


with

locations as (

    select * from {{ ref('stg_locations') }}

)

select * from locations
