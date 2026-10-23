{{ config(materialized='table', schema='marts') }}


-- Materialized copy of the Unified Star Schema bridge, in the marts layer.
--
-- The bridge is defined once, in intermediate/int_cafe_bridge.sql: `stage` first,
-- the six _key_cafe_* columns last, one row per record per reporting table.
-- This model only persists that definition as a table, so consumers read a final
-- materialized object instead of re-running a six-way UNION ALL over views on
-- every query. It adds no columns, no filters and no joins — the grain is
-- inherited unchanged from the intermediate model.
--
-- Never add logic here. Any change to the key contract belongs in the
-- intermediate model, where the tests and the row-shape rule live.

SELECT * FROM {{ ref('int_cafe_bridge') }}
