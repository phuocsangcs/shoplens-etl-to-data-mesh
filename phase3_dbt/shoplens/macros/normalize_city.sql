{#
  MACRO = "hàm" SQL tái sử dụng (viết bằng Jinja). Thay cho hàm normalize_city() trong transform.py phase 1.
  'São Paulo ' -> 'sao paulo'  |  'sa£o paulo' -> 'sao paulo'
  Dùng: {{ normalize_city('customer_city') }}
#}
{% macro normalize_city(column) -%}
    nullif(trim(regexp_replace(
        regexp_replace(strip_accents(lower({{ column }})), '[^a-z0-9 ''\-]', '', 'g'),
        '\s+', ' ', 'g')), '')
{%- endmacro %}
