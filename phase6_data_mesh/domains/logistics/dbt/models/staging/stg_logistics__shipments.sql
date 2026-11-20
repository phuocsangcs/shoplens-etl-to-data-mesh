-- One row per delivered order with its fulfillment milestones.
select
    order_id,
    order_purchase_timestamp       as purchased_at,
    order_delivered_carrier_date   as handed_to_carrier_at,
    order_delivered_customer_date  as delivered_at,
    order_estimated_delivery_date  as estimated_delivery_at
from {{ source('raw', 'orders') }}
where lower(trim(order_status)) = 'delivered'
  and order_delivered_customer_date is not null
