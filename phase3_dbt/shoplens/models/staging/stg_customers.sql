-- Staging: clean 1-1 with raw.customers. Rename columns, standardize values. NO joins, NO aggregation.
select
    customer_id,
    customer_unique_id,
    lpad(customer_zip_code_prefix, 5, '0')   as zip_code_prefix,
    {{ normalize_city('customer_city') }}     as city,
    upper(trim(customer_state))               as state
from {{ source('olist', 'customers') }}
