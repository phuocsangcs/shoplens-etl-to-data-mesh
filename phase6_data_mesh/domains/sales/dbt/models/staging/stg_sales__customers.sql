select
    customer_id,
    customer_unique_id,
    {{ dbt_platform.normalize_city('customer_city') }} as city,
    upper(trim(customer_state))                        as state
from {{ source('raw', 'customers') }}
