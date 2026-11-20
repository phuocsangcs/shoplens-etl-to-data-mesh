-- SINGULAR TEST: một câu SQL tự viết. Test ĐẠT khi query trả về 0 dòng.
-- Đối soát: tổng price trong fact phải khớp tổng price hợp lệ trong raw (không mất/thừa đồng nào).
with fact as (select round(sum(price), 2) as total from {{ ref('fact_order_items') }}),
     raw  as (select round(sum(price), 2) as total from {{ source('olist', 'order_items') }} where price > 0)
select fact.total as fact_total, raw.total as raw_total
from fact, raw
where fact.total <> raw.total
