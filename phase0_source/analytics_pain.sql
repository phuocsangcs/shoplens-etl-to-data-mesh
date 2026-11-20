-- =====================================================================
-- Phase 0: Thử làm "data analyst" ngay trên DB production của Olist.
-- Chạy:  docker exec -i shoplens-source-db psql -U shop -d shop < phase0_source/analytics_pain.sql
-- Mục tiêu: CẢM NHẬN được vì sao cần ETL + data warehouse. Mọi con số đều là data thật.
-- =====================================================================

\echo ''
\echo '=== NỖI ĐAU #1: DATA BẨN (có thật, không ai cố ý cài) ==='

\echo '--- 1a. Cùng một thành phố São Paulo, 4 cách viết (có cả lỗi encoding "sa£o") ---'
SELECT geolocation_city, COUNT(*) AS so_dong
FROM geolocation
WHERE geolocation_state = 'SP' AND geolocation_city IN ('sao paulo', 'são paulo', 'sãopaulo', 'sa£o paulo')
GROUP BY 1 ORDER BY 2 DESC;

\echo '--- 1b. Các lỗi khác ---'
SELECT 'Sản phẩm không có category'           AS van_de, COUNT(*) AS so_luong FROM products WHERE product_category_name IS NULL
UNION ALL
SELECT 'Category không có bản dịch tiếng Anh', COUNT(DISTINCT p.product_category_name)
  FROM products p LEFT JOIN product_category_name_translation t USING (product_category_name)
  WHERE p.product_category_name IS NOT NULL AND t.product_category_name IS NULL
UNION ALL
SELECT 'review_id bị trùng (tưởng là khoá chính)', COUNT(*) - COUNT(DISTINCT review_id) FROM order_reviews
UNION ALL
SELECT 'Đơn "delivered" nhưng không có ngày giao', COUNT(*) FROM orders
  WHERE order_status = 'delivered' AND order_delivered_customer_date IS NULL
UNION ALL
SELECT 'Đơn không có món hàng nào', COUNT(*) FROM orders o
  WHERE NOT EXISTS (SELECT 1 FROM order_items i WHERE i.order_id = o.order_id);
-- => Nếu mỗi analyst tự xử lý theo cách riêng -> mỗi báo cáo một con số.


\echo ''
\echo '=== NỖI ĐAU #2: BẪY customer_id: "tỉ lệ khách quay lại" ==='
-- Olist sinh customer_id MỚI cho MỖI ĐƠN. Người thật là customer_unique_id.
WITH per_id AS (
    SELECT c.customer_id AS k, COUNT(*) AS n FROM orders o JOIN customers c USING (customer_id) GROUP BY 1
), per_person AS (
    SELECT c.customer_unique_id AS k, COUNT(*) AS n FROM orders o JOIN customers c USING (customer_id) GROUP BY 1
)
SELECT 'SAI (theo customer_id)' AS cach_tinh,
       ROUND(100.0 * COUNT(*) FILTER (WHERE n > 1) / COUNT(*), 2) AS pct_khach_quay_lai
FROM per_id
UNION ALL
SELECT 'ĐÚNG (theo customer_unique_id)',
       ROUND(100.0 * COUNT(*) FILTER (WHERE n > 1) / COUNT(*), 2)
FROM per_person;
-- => Sai: 0% khách quay lại -> sếp kết luận "không ai mua lần 2". Nghiệp vụ ẩn trong data,
--    chỉ ai hiểu nguồn mới biết. Warehouse phải mã hoá hiểu biết này MỘT LẦN cho mọi người.


\echo ''
\echo '=== NỖI ĐAU #3: lỗi FAN-OUT khi JOIN -> doanh thu bị nhân lên ==='
-- 2,961 đơn có >1 dòng thanh toán. JOIN items x payments -> mỗi món bị lặp theo số lần thanh toán.
SELECT 'SAI (join payments để lọc)' AS cach_tinh,
       SUM(oi.price) AS doanh_thu_brl
FROM orders o
JOIN order_items oi    ON oi.order_id = o.order_id
JOIN order_payments op ON op.order_id = o.order_id
WHERE o.order_status = 'delivered'
UNION ALL
SELECT 'ĐÚNG (không join payments)',
       SUM(oi.price)
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.order_status = 'delivered';
-- => Phase 2 sẽ học khái niệm "GRAIN" để không bao giờ dính lỗi này.


\echo ''
\echo '=== NỖI ĐAU #4: câu hỏi đơn giản = JOIN 4 bảng + xử lý NULL + dịch tên ==='
-- "Top danh mục theo doanh thu năm 2018 (tên tiếng Anh)"
SELECT COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category,
       COUNT(DISTINCT o.order_id)  AS so_don,
       SUM(oi.price)               AS doanh_thu_brl
FROM orders o
JOIN order_items oi ON oi.order_id   = o.order_id
JOIN products p     ON p.product_id  = oi.product_id
LEFT JOIN product_category_name_translation t ON t.product_category_name = p.product_category_name
WHERE o.order_status = 'delivered'
  AND o.order_purchase_timestamp >= '2018-01-01'
GROUP BY 1
ORDER BY 3 DESC
LIMIT 10;


\echo ''
\echo '=== NỖI ĐAU #5: data "cụt" ở hai đầu: biểu đồ đánh lừa ==='
SELECT TO_CHAR(DATE_TRUNC('month', order_purchase_timestamp), 'YYYY-MM') AS thang,
       COUNT(*) AS so_don
FROM orders
GROUP BY 1 ORDER BY 1;
-- => 2018-09 chỉ 16 đơn, 2018-10 chỉ 4 đơn: không phải sàn sập, mà là bản export bị cắt.
--    Không có ai "đánh dấu" data đến ngày nào là đủ -> cần kiểm tra freshness/completeness (phase 5).


\echo ''
\echo '=== NỖI ĐAU #6: query phân tích chạy trên DB của app ==='
EXPLAIN (ANALYZE, COSTS OFF)
SELECT p.product_category_name, SUM(oi.price)
FROM order_items oi JOIN products p ON p.product_id = oi.product_id
GROUP BY 1;
-- "Seq Scan": đọc TOÀN BỘ bảng. Postgres lưu theo DÒNG (row-store): muốn SUM 1 cột price
-- vẫn phải đọc cả dòng (order_id, seller_id, dates...). Warehouse lưu theo CỘT -> chỉ đọc cột cần.
-- Ở quy mô thật (trăm triệu dòng), query này giành CPU/IO với khách đang đặt hàng.

-- (Thêm: DB này chỉ có trạng thái HIỆN TẠI. Khách đổi địa chỉ -> UPDATE đè -> lịch sử mất.
--  Phase 3 giải bằng SCD Type 2.)
