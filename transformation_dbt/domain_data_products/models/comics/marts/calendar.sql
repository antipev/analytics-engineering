{{ config(
    materialized='table',
    schema='staging') }}

{{ calendar_macro(start_date="date '2006-01-01'", end_date="current_date()") }}
