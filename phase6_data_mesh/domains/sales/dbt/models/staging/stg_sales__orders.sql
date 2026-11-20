select
    order_id,
    customer_id,
    lower(trim(order_status)) as order_status,
    order_purchase_timestamp  as purchased_at
from {{ source('raw', 'orders') }}
