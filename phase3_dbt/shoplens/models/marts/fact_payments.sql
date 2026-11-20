-- GRAIN: one payment
select
    p.order_id,
    p.payment_sequential,
    cast(strftime(o.order_purchase_timestamp, '%Y%m%d') as integer) as order_date_key,
    coalesce(dc.customer_key, '-1') as customer_key,
    p.payment_type,
    p.payment_installments,
    p.payment_value
from {{ ref('stg_order_payments') }} p
join {{ ref('stg_orders') }} o using (order_id)
left join {{ ref('stg_customers') }} c using (customer_id)
left join {{ ref('dim_customer') }} dc
       on dc.customer_unique_id = c.customer_unique_id
      and o.order_purchase_timestamp >= dc.valid_from
      and o.order_purchase_timestamp <  dc.valid_to
