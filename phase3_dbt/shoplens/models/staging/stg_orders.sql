select
    o.order_id,
    o.customer_id,
    lower(trim(o.order_status))       as order_status,
    o.order_purchase_timestamp,
    o.order_approved_at,
    o.order_delivered_carrier_date,
    o.order_delivered_customer_date,
    o.order_estimated_delivery_date,
    -- cờ chất lượng: đánh dấu, không xoá
    o.order_id in (select order_id from {{ source('olist', 'order_items') }})            as has_items,
    lower(trim(o.order_status)) = 'delivered' and o.order_delivered_customer_date is null as is_delivered_missing_date
from {{ source('olist', 'orders') }} o
