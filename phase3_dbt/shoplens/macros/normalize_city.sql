{#
  MACRO = reusable SQL "function" (written in Jinja). Replaces normalize_city() in phase 1 transform.py.
  Strips accents, lowercases, keeps only letters/digits/space/'/-, collapses whitespace.
  Usage: {{ normalize_city('customer_city') }}
#}
{% macro normalize_city(column) -%}
    nullif(trim(regexp_replace(
        regexp_replace(strip_accents(lower({{ column }})), '[^a-z0-9 ''\-]', '', 'g'),
        '\s+', ' ', 'g')), '')
{%- endmacro %}
