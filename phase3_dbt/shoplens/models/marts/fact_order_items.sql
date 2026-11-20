-- =====================================================================
-- fact_order_items. GRAIN: one item in one order.
--
-- INCREMENTAL MODEL: first run builds everything; later runs ONLY process orders newer than the newest one already loaded.
-- This is the phase 1 "watermark", but dbt handles it: {{ this }} = this table,
-- is_incremental() = true once the table exists. delete+insert on unique_key -> idempotent.
-- =====================================================================
{{ config(
    materialized='incremental',
    unique_key=['order_id', 'order_item_id'],
    incremental_strategy='delete+insert'
) }}

with orders as (
    select * from {{ ref('stg_orders') }}
    {% if is_incremental() %}
    where order_purchase_timestamp > (select max(order_purchase_timestamp) from {{ this }})
    {% endif %}
)

select
    oi.order_id,
    oi.order_item_id,
    o.order_purchase_timestamp,
    cast(strftime(o.order_purchase_timestamp, '%Y%m%d') as integer) as order_date_key,
    coalesce(dc.customer_key, '-1') as customer_key,
    coalesce(dp.product_key, '-1')  as product_key,
    coalesce(ds.seller_key, '-1')   as seller_key,
    o.order_status,
    oi.price,
    oi.freight_value,
    oi.price + oi.freight_value     as total_value
from orders o
join {{ ref('stg_order_items') }} oi using (order_id)
left join {{ ref('stg_customers') }} c using (customer_id)
-- SCD2 join: pick the address version that was VALID at purchase time
left join {{ ref('dim_customer') }} dc
       on dc.customer_unique_id = c.customer_unique_id
      and o.order_purchase_timestamp >= dc.valid_from
      and o.order_purchase_timestamp <  dc.valid_to
left join {{ ref('dim_product') }} dp on dp.product_id = oi.product_id
left join {{ ref('dim_seller') }}  ds on ds.seller_id  = oi.seller_id
