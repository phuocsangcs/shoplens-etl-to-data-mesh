-- =====================================================================
-- DIMENSION: dim_customer. GRAIN: mỗi dòng = 1 NGƯỜI (customer_unique_id)
--
-- Đây là chỗ "diệt" bẫy customer_id của phase 0:
--   Nguồn: 99,441 customer_id (mỗi đơn 1 id)  ->  Ở đây: 96,096 người thật.
--   Hiểu biết nghiệp vụ được mã hoá MỘT LẦN, mọi analyst dùng chung, không ai phải nhớ nữa.
--
-- customer_key = SURROGATE KEY (khoá thay thế): số nguyên do warehouse tự sinh,
--   độc lập với id của hệ thống nguồn. Lợi ích: JOIN nhanh, và nếu mai gộp thêm nguồn khác
--   (app mobile có id kiểu khác) thì vẫn chung một khoá.
--
-- SCD Type 1: thành phố = nơi ở trong ĐƠN GẦN NHẤT (ghi đè, không giữ lịch sử).
--   Phase 3 sẽ nâng lên SCD Type 2 (giữ lịch sử).
-- =====================================================================
CREATE OR REPLACE TABLE mart.dim_customer AS
WITH per_order AS (
    SELECT c.customer_unique_id, c.customer_city, c.customer_state, c.customer_zip_code_prefix,
           o.order_purchase_timestamp,
           ROW_NUMBER() OVER (PARTITION BY c.customer_unique_id
                              ORDER BY o.order_purchase_timestamp DESC) AS recency_rank
    FROM clean.customers c
    LEFT JOIN clean.orders o USING (customer_id)
),
stats AS (
    SELECT customer_unique_id,
           MIN(order_purchase_timestamp)   AS first_order_at,
           MAX(order_purchase_timestamp)   AS last_order_at,
           COUNT(order_purchase_timestamp) AS order_count
    FROM per_order GROUP BY 1
)
SELECT
    ROW_NUMBER() OVER (ORDER BY p.customer_unique_id) AS customer_key,
    p.customer_unique_id,
    p.customer_city            AS city,
    p.customer_state           AS state,
    p.customer_zip_code_prefix AS zip_code_prefix,
    s.first_order_at,
    s.last_order_at,
    s.order_count,
    s.order_count > 1          AS is_repeat_customer
FROM per_order p
JOIN stats s USING (customer_unique_id)
WHERE p.recency_rank = 1

UNION ALL
-- "Unknown member": dòng đặc biệt key = -1 cho trường hợp fact không tìm thấy khách.
-- Nhờ vậy fact luôn JOIN được (INNER JOIN không bao giờ làm rơi mất doanh thu).
SELECT -1, 'unknown', 'unknown', 'unknown', '00000', NULL, NULL, 0, FALSE;
