-- =====================================================================
-- DATA PRODUCT (output port): logistics.delivery_performance v1
-- Combines Logistics' own data with Sales' published data product (sales.orders v1).
-- Note: we only use columns PROMISED in the Sales contract (customer_state, review_score).
-- =====================================================================
select
    s.order_id,
    o.seller_state,
    so.customer_state,
    o.seller_state <> so.customer_state                                         as is_interstate,
    s.purchased_at,
    s.handed_to_carrier_at,
    s.delivered_at,
    s.estimated_delivery_at,
    date_diff('hour', s.purchased_at, s.delivered_at) / 24.0                    as delivery_days,
    s.delivered_at::date > s.estimated_delivery_at::date                        as is_late,
    so.review_score,
    {{ dbt_platform.published_at() }}
from {{ ref('stg_logistics__shipments') }} s
left join {{ ref('stg_logistics__order_origin') }} o using (order_id)
left join {{ source('sales', 'orders_v1') }} so using (order_id)
