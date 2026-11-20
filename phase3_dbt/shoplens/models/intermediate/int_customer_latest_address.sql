-- Mỗi NGƯỜI (customer_unique_id) 1 dòng, với địa chỉ HIỆN TẠI (lấy từ đơn gần nhất).
-- Đây là "trạng thái hiện tại" mà snapshot sẽ chụp lại mỗi lần chạy để phát hiện thay đổi.
select
    c.customer_unique_id,
    c.city,
    c.state,
    c.zip_code_prefix
from {{ ref('stg_customers') }} c
left join {{ ref('stg_orders') }} o using (customer_id)
qualify row_number() over (
    partition by c.customer_unique_id
    order by o.order_purchase_timestamp desc nulls last, c.customer_id
) = 1
