-- =====================================================================
-- DATA PRODUCT (output port): sales.orders v1
-- The ONLY table other domains are allowed to read. Its shape is guarded by a dbt
-- model contract (see _output.yml): if this SELECT stops matching the declared
-- columns/types, `dbt build` FAILS before anything is published.
--
-- Demo of a breaking change:  dbt build --vars "{simulate_breaking_change: true}"
-- =====================================================================
select
    o.order_id,
    c.customer_unique_id,
    c.state                       as customer_state,
    o.purchased_at,
    o.order_status,
    cast(t.item_count as integer) as item_count,
    {% if var('simulate_breaking_change', false) %}
    t.items_value                 as gross_merchandise_value,   -- someone "just renames a column"
    {% else %}
    t.items_value,
    {% endif %}
    t.freight_value,
    t.payment_value,
    cast(t.review_score as integer) as review_score,
    {{ dbt_platform.published_at() }}
from {{ ref('stg_sales__orders') }} o
join {{ ref('stg_sales__customers') }} c using (customer_id)
join {{ ref('stg_sales__order_totals') }} t using (order_id)
