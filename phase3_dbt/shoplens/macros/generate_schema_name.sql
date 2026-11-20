{#
  Mặc định dbt đặt tên schema = "<schema mặc định>_<schema tuỳ chỉnh>" (vd: main_staging).
  Macro này ghi đè để dùng đúng tên: staging, intermediate, marts, snapshots, seeds.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
