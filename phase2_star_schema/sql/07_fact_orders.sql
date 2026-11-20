-- =====================================================================
-- FACT: fact_orders (kiểu "accumulating snapshot")
-- GRAIN: mỗi dòng = 1 ĐƠN HÀNG, theo dõi vòng đời đơn qua các mốc:
--        mua → duyệt → giao cho hãng vận chuyển → khách nhận   (so với ngày dự kiến)
--
-- Số liệu từ items/payments được TỔNG HỢP LÊN grain đơn TRƯỚC khi JOIN
-- -> không bao giờ fan-out (mỗi CTE trả về đúng 1 dòng / đơn).
-- Đây là fact chính cho câu hỏi về GIAO HÀNG (bộ phận logistics).
-- =====================================================================
CREATE OR REPLACE TABLE mart.fact_orders AS
WITH items AS (
    SELECT order_id, COUNT(*) AS item_count, SUM(price) AS items_value, SUM(freight_value) AS freight_value
    FROM clean.order_items GROUP BY 1
),
pays AS (
    SELECT order_id, SUM(payment_value) AS payment_value, COUNT(*) AS payment_count
    FROM clean.order_payments GROUP BY 1
)
SELECT
    o.order_id,
    COALESCE(dc.customer_key, -1)                                            AS customer_key,
    CAST(strftime(o.order_purchase_timestamp, '%Y%m%d') AS INTEGER)          AS purchase_date_key,
    CAST(strftime(o.order_delivered_customer_date, '%Y%m%d') AS INTEGER)     AS delivered_date_key,
    CAST(strftime(o.order_estimated_delivery_date, '%Y%m%d') AS INTEGER)     AS estimated_date_key,
    o.order_status,
    -- measures: tiền
    COALESCE(i.item_count, 0)        AS item_count,
    COALESCE(i.items_value, 0)       AS items_value,
    COALESCE(i.freight_value, 0)     AS freight_value,
    COALESCE(p.payment_value, 0)     AS payment_value,
    COALESCE(p.payment_count, 0)     AS payment_count,
    -- measures: thời gian giao hàng (NULL nếu chưa giao)
    date_diff('hour', o.order_purchase_timestamp, o.order_approved_at) / 24.0              AS approval_days,
    date_diff('hour', o.order_purchase_timestamp, o.order_delivered_customer_date) / 24.0  AS delivery_days,
    CASE WHEN o.order_delivered_customer_date IS NULL THEN NULL
         ELSE o.order_delivered_customer_date::DATE > o.order_estimated_delivery_date::DATE END AS is_late,
    -- review (đã là 1 review / đơn nhờ phase 1)
    r.review_score,
    -- cờ chất lượng mang từ phase 1
    o.has_items,
    o.is_delivered_missing_date
FROM clean.orders o
LEFT JOIN items i              USING (order_id)
LEFT JOIN pays p               USING (order_id)
LEFT JOIN clean.order_reviews r USING (order_id)
LEFT JOIN clean.customers c    USING (customer_id)
LEFT JOIN mart.dim_customer dc ON dc.customer_unique_id = c.customer_unique_id;
