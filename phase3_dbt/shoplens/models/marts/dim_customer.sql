-- =====================================================================
-- dim_customer: SCD TYPE 2. GRAIN: mỗi dòng = 1 PHIÊN BẢN địa chỉ của 1 người.
--
-- Khác phase 2 (SCD1, 1 người = 1 dòng, ghi đè):
--   khách chuyển SP -> RJ  =>  2 dòng:  [SP, valid 1900..ngày chuyển]  [RJ, valid ngày chuyển..9999]
--   Đơn mua TRƯỚC ngày chuyển gắn với phiên bản SP, đơn SAU gắn với RJ. Lịch sử không bị viết lại.
--
-- customer_key = dbt_scd_id: hash do dbt sinh (unique_key + thời điểm). Ổn định qua các lần chạy,
-- khác ROW_NUMBER() ở phase 2 (đổi số mỗi lần dựng lại -> không dùng được với fact incremental).
-- =====================================================================
with snap as (
    select * from {{ ref('snap_customer_address') }}
),

order_stats as (
    select
        c.customer_unique_id,
        min(o.order_purchase_timestamp) as first_order_at,
        max(o.order_purchase_timestamp) as last_order_at,
        count(*)                        as order_count
    from {{ ref('stg_orders') }} o
    join {{ ref('stg_customers') }} c using (customer_id)
    group by 1
)

select
    s.dbt_scd_id                                    as customer_key,
    s.customer_unique_id,
    s.city,
    s.state,
    s.zip_code_prefix,
    -- Phiên bản đầu tiên coi như có hiệu lực "từ xưa": dữ liệu lịch sử nạp lần đầu
    -- vẫn phải gắn được vào phiên bản đó (snapshot chỉ bắt đầu chụp từ hôm nay).
    case when row_number() over (partition by s.customer_unique_id order by s.dbt_valid_from) = 1
         then timestamp '1900-01-01' else s.dbt_valid_from end as valid_from,
    coalesce(s.dbt_valid_to, timestamp '9999-12-31') as valid_to,
    s.dbt_valid_to is null                           as is_current,
    st.first_order_at,
    st.last_order_at,
    coalesce(st.order_count, 0)                      as order_count,
    coalesce(st.order_count, 0) > 1                  as is_repeat_customer
from snap s
left join order_stats st using (customer_unique_id)

union all

select '-1', 'unknown', 'unknown', 'unknown', '00000',
       timestamp '1900-01-01', timestamp '9999-12-31', true, null, null, 0, false
