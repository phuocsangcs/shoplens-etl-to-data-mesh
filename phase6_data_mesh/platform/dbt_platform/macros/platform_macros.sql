{#
  Platform macros shared by all domains.
#}

{# Every data product must expose when it was published (global policy). #}
{% macro published_at() -%}
    cast(now() as timestamp) as _published_at
{%- endmacro %}

{# Standard city normalization: strip accents, lowercase, keep [a-z0-9 '-], collapse spaces. #}
{% macro normalize_city(column) -%}
    nullif(trim(regexp_replace(
        regexp_replace(strip_accents(lower({{ column }})), '[^a-z0-9 ''\-]', '', 'g'),
        '\s+', ' ', 'g')), '')
{%- endmacro %}
