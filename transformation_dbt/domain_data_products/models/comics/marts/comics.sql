{{ config(
    materialized='incremental',
    unique_key='_key_comics',
    schema='staging'
) }}

WITH

intermediate AS (

    
    SELECT 
    --- original columns
      month,
      num,
      link,	
      year,	
      news,	
      safe_title,	
      transcript,	
      --alt,	
      --img,	
      title,	
      day,	
      extra_parts,

    --- new columns
      publication_date, 
      is_valid_date, 
      tooltip_text,
      img_url,
      nr_news,
      nr_links,
      nr_extra_parts,
      transcript_characters_count,
      transcript_word_count,
      tooltip_characters_count,
      tooltip_word_count,
      title_characters_count,
      title_word_count,
      updated_at,
    --- keys
      _key_comics,
      publication_date AS _key_calendar

    FROM {{ ref('int_comics') }}

),

final AS (

    SELECT
      *
    FROM intermediate

)

SELECT
  * 
FROM final
