{% macro calendar_macro(start_date, end_date) %}

WITH
    calendar_date AS (

        {{ date_spine(start_date, end_date) }}

    ),

    dim_calendar AS (

        SELECT

            CAST(dt AS DATE)                                                       AS _key_calendar,
            {{ date_trunc('month', 'dt') }}                                    AS calendar_monthly_key,
            dt                                                                      AS {{ quote_identifier('date') }},
            CASE WHEN dt <= CURRENT_DATE() THEN 'Past' ELSE 'Future' END            AS past_future,
            EXTRACT(YEAR FROM dt)                                                   AS year,
            LEFT(CAST(dt AS STRING), 7)                                             AS year_month,

            {{ date_format('dt', '%A') }}                                       AS day_of_week,
            {{ date_format('dt', '%a') }}                                       AS day_of_week_abbrv,
            EXTRACT(DAY FROM dt)                                                    AS day_number_in_month,
            {{ iso_day_of_week('dt') }}                                         AS day_number_in_week,
            {{ iso_week('dt') }}                                                AS {{ quote_identifier('week') }},

            {{ week_start('dt') }}                                              AS week_start,
            {{ date_add('day', 6, week_start('dt')) }}                      AS week_end,

            EXTRACT(MONTH FROM dt)                                                  AS month_number,
            {{ date_format('dt', '%B') }}                                       AS month,
            {{ date_format('dt', '%b') }}                                       AS month_abbrv,
            {{ date_format('dt', '%b %Y') }}                                    AS month_year,
            {{ date_trunc('month', 'dt') }}                                     AS month_start,
            {{ last_day('dt', 'month') }}                                       AS month_end,

            EXTRACT(QUARTER FROM dt)                                                AS quarter_number,
            {{ date_trunc('quarter', 'dt') }}                                   AS quarter_start,
            {{ last_day('dt', 'quarter') }}                                     AS quarter_end,

            {{ date_trunc('year', 'dt') }}                                      AS year_start,
            {{ last_day('dt', 'year') }}                                        AS year_end,

            {{ iso_week(date_add('week', -1, 'dt')) }}                      AS last_week_date,
            {{ week_start(date_add('week', -1, 'dt')) }}                    AS last_week_start,
            {{ date_add('day', 6, week_start(date_add('week', -1, 'dt'))) }} AS last_week_end,

            {{ date_add('month', -1, 'dt') }}                                   AS last_month_date,
            {{ date_trunc('month', date_add('month', -1, 'dt')) }}          AS last_month_start,
            {{ last_day(date_add('month', -1, 'dt'), 'month') }}            AS last_month_end,

            {{ date_add('quarter', -1, 'dt') }}                                 AS last_quarter_date,
            {{ date_trunc('quarter', date_add('quarter', -1, 'dt')) }}      AS last_quarter_start,
            {{ last_day(date_add('quarter', -1, 'dt'), 'quarter') }}        AS last_quarter_end,

            {{ date_add('year', -1, 'dt') }}                                    AS last_year_date,
            {{ week_start(date_add('year', -1, 'dt')) }}                    AS last_year_week_start,
            {{ date_add('day', 6, week_start(date_add('year', -1, 'dt'))) }} AS last_year_week_end,
            {{ date_trunc('month', date_add('year', -1, 'dt')) }}           AS last_year_month_start,
            {{ last_day(date_add('year', -1, 'dt'), 'month') }}             AS last_year_month_end,
            {{ date_trunc('quarter', date_add('year', -1, 'dt')) }}         AS last_year_quarter_start,
            {{ last_day(date_add('year', -1, 'dt'), 'quarter') }}           AS last_year_quarter_end,
            {{ date_trunc('year', date_add('year', -1, 'dt')) }}            AS last_year_year_start,
            {{ last_day(date_add('year', -1, 'dt'), 'year') }}              AS last_year_year_end,

            CURRENT_DATE()                                                          AS current_year_today,
            {{ date_add('day', -1, 'current_date()') }}                         AS current_year_yesterday,
            {{ week_start('current_date()') }}                                  AS current_year_week_start,
            {{ date_add('day', 6, week_start('current_date()')) }}          AS current_year_week_end,
            {{ date_trunc('month', 'current_date()') }}                         AS current_year_month_start,
            {{ last_day('current_date()', 'month') }}                           AS current_year_month_end,
            {{ date_trunc('quarter', 'current_date()') }}                       AS current_year_quarter_start,
            {{ last_day('current_date()', 'quarter') }}                         AS current_year_quarter_end,
            {{ date_trunc('year', 'current_date()') }}                          AS current_year_year_start,
            {{ last_day('current_date()', 'year') }}                            AS current_year_year_end,

            {{ date_add('week', -1, week_start('current_date()')) }}        AS current_year_last_week_start,
            {{ date_add('day', 6, date_add('week', -1, week_start('current_date()'))) }} AS current_year_last_week_end,
            {{ date_trunc('month', date_add('month', -1, 'current_date()')) }} AS current_year_last_month_start,
            {{ date_add('month', -1, last_day('current_date()', 'month')) }} AS current_year_last_month_end,
            {{ date_trunc('quarter', date_add('quarter', -1, 'current_date()')) }} AS current_year_last_quarter_start,
            {{ date_add('quarter', -1, last_day('current_date()', 'quarter')) }} AS current_year_last_quarter_end,

            {{ date_add('year', -1, 'current_date()') }}                        AS current_year_today_in_last_year,
            {{ date_add('day', -1, date_add('year', -1, 'current_date()')) }} AS current_year_yesterday_in_last_year,
            {{ week_start(date_add('year', -1, 'current_date()')) }}        AS current_year_week_start_in_last_year,
            {{ date_add('day', 6, week_start(date_add('year', -1, 'current_date()'))) }} AS current_year_week_end_in_last_year,
            {{ date_trunc('month', date_add('year', -1, 'current_date()')) }} AS current_year_month_start_in_last_year,
            {{ last_day(date_add('year', -1, 'current_date()'), 'month') }} AS current_year_month_end_in_last_year,
            {{ date_trunc('quarter', date_add('year', -1, 'current_date()')) }} AS current_year_quarter_start_in_last_year,
            {{ last_day(date_add('year', -1, 'current_date()'), 'quarter') }} AS current_year_quarter_end_in_last_year,
            {{ date_trunc('year', date_add('year', -1, 'current_date()')) }} AS current_year_year_start_in_last_year,
            {{ last_day(date_add('year', -1, 'current_date()'), 'year') }}  AS current_year_year_end_in_last_year

        FROM calendar_date

    )

SELECT *
FROM dim_calendar
ORDER BY {{ quote_identifier('date') }}

{% endmacro %}


{% macro date_spine(start_date, end_date) %}
    {%- if target.type == 'bigquery' -%}
        SELECT dt FROM UNNEST(GENERATE_DATE_ARRAY({{ start_date }}, {{ end_date }})) AS dt
    {%- else -%}
        SELECT CAST({{ start_date }} + CAST(UNNEST(GENERATE_SERIES(0, DATEDIFF('day', {{ start_date }}, {{ end_date }}))) AS INTEGER) AS DATE) AS dt
    {%- endif -%}
{% endmacro %}


{% macro date_trunc(part, d) %}
    {%- if target.type == 'bigquery' -%}
        DATE_TRUNC({{ d }}, {{ part | upper }})
    {%- else -%}
        CAST(DATE_TRUNC('{{ part }}', {{ d }}) AS DATE)
    {%- endif -%}
{% endmacro %}


{% macro date_add(part, n, d) %}
    {%- if target.type == 'bigquery' -%}
        DATE_ADD({{ d }}, INTERVAL {{ n }} {{ part | upper }})
    {%- else -%}
        {%- set unit = part | lower -%}
        {%- if unit == 'quarter' -%}
            CAST(({{ d }} + (CAST({{ n }} AS INTEGER) * 3) * INTERVAL 1 MONTH) AS DATE)
        {%- elif unit == 'week' -%}
            CAST(({{ d }} + (CAST({{ n }} AS INTEGER) * 7) * INTERVAL 1 DAY) AS DATE)
        {%- else -%}
            CAST(({{ d }} + CAST({{ n }} AS INTEGER) * INTERVAL 1 {{ unit }}) AS DATE)
        {%- endif -%}
    {%- endif -%}
{% endmacro %}


{% macro last_day(d, part) %}
    {%- if target.type == 'bigquery' -%}
        LAST_DAY({{ d }}, {{ part | upper }})
    {%- else -%}
        {{ date_add('day', -1, date_add(part, 1, date_trunc(part, d))) }}
    {%- endif -%}
{% endmacro %}


{% macro date_format(d, fmt) %}
    {%- if target.type == 'bigquery' -%}
        FORMAT_DATE('{{ fmt }}', {{ d }})
    {%- else -%}
        STRFTIME({{ d }}, '{{ fmt }}')
    {%- endif -%}
{% endmacro %}


{% macro iso_week(d) %}
    {%- if target.type == 'bigquery' -%}
        EXTRACT(ISOWEEK FROM {{ d }})
    {%- else -%}
        EXTRACT(WEEK FROM {{ d }})
    {%- endif -%}
{% endmacro %}


{% macro iso_day_of_week(d) %}
    {%- if target.type == 'bigquery' -%}
        EXTRACT(DAYOFWEEK FROM DATE_SUB({{ d }}, INTERVAL 1 DAY))
    {%- else -%}
        EXTRACT(ISODOW FROM {{ d }})
    {%- endif -%}
{% endmacro %}


{% macro week_start(d) %}
    {%- if target.type == 'bigquery' -%}
        DATE_TRUNC({{ d }}, ISOWEEK)
    {%- else -%}
        CAST(DATE_TRUNC('week', {{ d }}) AS DATE)
    {%- endif -%}
{% endmacro %}


{% macro quote_identifier(identifier) %}
    {%- if target.type == 'bigquery' -%}`{{ identifier }}`{%- else -%}"{{ identifier }}"{%- endif -%}
{% endmacro %}
