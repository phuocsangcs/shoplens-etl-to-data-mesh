-- One row per PERSON (customer_unique_id) with their CURRENT address (taken from the latest order).
-- This is the "current state" the snapshot captures on every run to detect changes.
-- customer_id is the tie-breaker: without it, two orders in the same second make the result non-deterministic.
select
    c.customer_unique_id,
    c.city,
    c.state,
    c.zip_code_prefix
from {{ ref('stg_customers') }} c
left join {{ ref('stg_orders') }} o using (customer_id)
qualify row_number() over (
    partition by c.customer_unique_id
    order by o.order_purchase_timestamp desc nulls last, c.customer_id
) = 1
