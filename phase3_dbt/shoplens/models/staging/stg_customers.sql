-- Staging: làm sạch 1-1 với raw.customers. Đổi tên cột cho gọn, chuẩn hoá giá trị. KHÔNG join, KHÔNG gộp.
select
    customer_id,
    customer_unique_id,
    lpad(customer_zip_code_prefix, 5, '0')   as zip_code_prefix,
    {{ normalize_city('customer_city') }}     as city,
    upper(trim(customer_state))               as state
from {{ source('olist', 'customers') }}
