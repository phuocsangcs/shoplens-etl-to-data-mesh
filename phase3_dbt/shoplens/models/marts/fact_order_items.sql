-- =====================================================================
-- fact_order_items. GRAIN: 1 món trong 1 đơn.
--
-- INCREMENTAL MODEL: lần đầu dựng toàn bộ; các lần sau CHỈ xử lý đơn mới hơn đơn mới nhất đã có.
-- Đây chính là "watermark" của phase 1, nhưng dbt lo hết: {{ this }} = chính bảng này,
-- is_incremental() = true khi bảng đã tồn tại. delete+insert theo unique_key -> idempotent.
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
-- JOIN SCD2: lấy phiên bản địa chỉ ĐANG HIỆU LỰC tại thời điểm mua
left join {{ ref('dim_customer') }} dc
       on dc.customer_unique_id = c.customer_unique_id
      and o.order_purchase_timestamp >= dc.valid_from
      and o.order_purchase_timestamp <  dc.valid_to
left join {{ ref('dim_product') }} dp on dp.product_id = oi.product_id
left join {{ ref('dim_seller') }}  ds on ds.seller_id  = oi.seller_id
