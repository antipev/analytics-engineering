{{ config(
    materialized='view',
    schema='staging'
) }}

WITH

staging AS (

    
    SELECT 
    --- original columns
      month,
      num,
      link,	
      year,	
      news,	
      safe_title,	
      transcript,	
      alt,	
      img,	
      title,	
      day,	
      extra_parts, 
    FROM {{ ref('stg_comics') }}

),

new_columns AS (

    SELECT
    --- original columns
      *,
    --- new columns 
      
      CASE 
            WHEN TRY_CAST(year AS BIGINT) IS NOT NULL 
             AND TRY_CAST(month AS BIGINT) BETWEEN 1 AND 12 
             AND TRY_CAST(day AS BIGINT) BETWEEN 1 AND 31 
            THEN MAKE_DATE(TRY_CAST(year AS BIGINT), TRY_CAST(month AS BIGINT), TRY_CAST(day AS BIGINT))
            ELSE NULL
        END                         AS publication_date, -- (returns NULL if components are out of range)
 
        CASE 
            WHEN TRY_CAST(year AS BIGINT) IS NOT NULL 
             AND TRY_CAST(month AS BIGINT) BETWEEN 1 AND 12 
             AND TRY_CAST(day AS BIGINT) BETWEEN 1 AND 31 
            THEN TRUE
            ELSE FALSE
        END                         AS is_valid_date, -- to check if the date is valid (TRUE/FALSE)

      alt                           AS tooltip_text,
      img                           AS img_url,
      IF(news IS NULL, 0,1)         AS nr_news,
      IF(link IS NULL, 0,1)         AS nr_links,
      IF(extra_parts IS NULL, 0,1)  AS nr_extra_parts,

      ---
      -- Character counts
      LENGTH(transcript)            AS transcript_characters_count,
      ARRAY_LENGTH(
        STRING_SPLIT(
            TRIM(transcript), ' ')) AS transcript_word_count,
    
      LENGTH(alt)                   AS tooltip_characters_count,
      ARRAY_LENGTH(
        STRING_SPLIT(
            TRIM(alt), ' '))        AS tooltip_word_count,
     
      LENGTH(title)                 AS title_characters_count,
      ARRAY_LENGTH(
        STRING_SPLIT(
            TRIM(title), ' '))      AS title_word_count,
      
      CURRENT_TIMESTAMP             AS updated_at,-- a timestamp indicating when a record was last updated

      num                           AS _key_comics,
    
    FROM staging

)

SELECT
  * 
FROM new_columns
