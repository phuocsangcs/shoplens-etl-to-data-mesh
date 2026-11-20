-- GRAIN: one order (order lifecycle). Items/payments are aggregated to order grain BEFORE joining -> no fan-out.
with items as (
    select order_id, count(*) as item_count, sum(price) as items_value, sum(freight_value) as freight_value
    from {{ ref('stg_order_items') }} group by 1
),
pays as (
    select order_id, sum(payment_value) as payment_value, count(*) as payment_count
    from {{ ref('stg_order_payments') }} group by 1
)

select
    o.order_id,
    coalesce(dc.customer_key, '-1')                                          as customer_key,
    cast(strftime(o.order_purchase_timestamp, '%Y%m%d') as integer)          as purchase_date_key,
    cast(strftime(o.order_delivered_customer_date, '%Y%m%d') as integer)     as delivered_date_key,
    cast(strftime(o.order_estimated_delivery_date, '%Y%m%d') as integer)     as estimated_date_key,
    o.order_status,
    coalesce(i.item_count, 0)       as item_count,
    coalesce(i.items_value, 0)      as items_value,
    coalesce(i.freight_value, 0)    as freight_value,
    coalesce(p.payment_value, 0)    as payment_value,
    coalesce(p.payment_count, 0)    as payment_count,
    date_diff('hour', o.order_purchase_timestamp, o.order_approved_at) / 24.0             as approval_days,
    date_diff('hour', o.order_purchase_timestamp, o.order_delivered_customer_date) / 24.0 as delivery_days,
    case when o.order_delivered_customer_date is null then null
         else o.order_delivered_customer_date::date > o.order_estimated_delivery_date::date end as is_late,
    r.review_score,
    o.has_items,
    o.is_delivered_missing_date
from {{ ref('stg_orders') }} o
left join items i using (order_id)
left join pays p  using (order_id)
left join {{ ref('stg_order_reviews') }} r using (order_id)
left join {{ ref('stg_customers') }} c using (customer_id)
left join {{ ref('dim_customer') }} dc
       on dc.customer_unique_id = c.customer_unique_id
      and o.order_purchase_timestamp >= dc.valid_from
      and o.order_purchase_timestamp <  dc.valid_to
