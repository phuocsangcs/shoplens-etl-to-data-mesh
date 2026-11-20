{#
  By default dbt names schemas "<default schema>_<custom schema>" (e.g. main_staging).
  This override uses the custom name as-is: staging, intermediate, marts, snapshots, seeds.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
