-- Aggregate items, payments and reviews to ORDER grain separately, then join 1-1 (no fan-out).
with items as (
    select order_id,
           count(*)                    as item_count,
           sum(price::double)          as items_value,
           sum(freight_value::double)  as freight_value
    from {{ source('raw', 'order_items') }}
    where price > 0
    group by 1
),
payments as (
    select order_id, sum(payment_value::double) as payment_value
    from {{ source('raw', 'order_payments') }}
    where payment_type <> 'not_defined'
    group by 1
),
reviews as (
    select order_id, review_score
    from {{ source('raw', 'order_reviews') }}
    qualify row_number() over (partition by order_id order by review_answer_timestamp desc) = 1
)
select
    o.order_id,
    coalesce(i.item_count, 0)    as item_count,
    coalesce(i.items_value, 0)   as items_value,
    coalesce(i.freight_value, 0) as freight_value,
    coalesce(p.payment_value, 0) as payment_value,
    r.review_score
from {{ source('raw', 'orders') }} o
left join items i    using (order_id)
left join payments p using (order_id)
left join reviews r  using (order_id)
