-- SINGULAR TEST: a hand-written SQL query. The test PASSES when the query returns 0 rows.
-- Reconciliation: total price in the fact must equal total valid price in raw (no money lost or added).
with fact as (select round(sum(price), 2) as total from {{ ref('fact_order_items') }}),
     raw  as (select round(sum(price), 2) as total from {{ source('olist', 'order_items') }} where price > 0)
select fact.total as fact_total, raw.total as raw_total
from fact, raw
where fact.total <> raw.total
