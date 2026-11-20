-- =====================================================================
-- FACT: fact_order_items
-- GRAIN: mỗi dòng = 1 MÓN HÀNG trong 1 đơn.   ← câu quan trọng nhất khi thiết kế fact
--
-- Fact chứa 2 loại cột:
--   - Khoá tới các dimension (customer_key, product_key, seller_key, order_date_key)
--   - MEASURES: con số cộng được (price, freight_value)
-- order_id, order_status: "degenerate dimension", tức thuộc tính của sự kiện, không đáng làm bảng dim riêng.
--
-- Fact này KHÔNG chứa payments: payments có grain khác (mỗi lần thanh toán).
-- Trộn 2 grain vào 1 bảng = fan-out (nỗi đau #3). Mỗi grain một fact riêng.
-- =====================================================================
CREATE OR REPLACE TABLE mart.fact_order_items AS
SELECT
    oi.order_id,
    oi.order_item_id,
    CAST(strftime(o.order_purchase_timestamp, '%Y%m%d') AS INTEGER) AS order_date_key,
    COALESCE(dc.customer_key, -1) AS customer_key,
    COALESCE(dp.product_key, -1)  AS product_key,
    COALESCE(ds.seller_key, -1)   AS seller_key,
    o.order_status,
    oi.price,
    oi.freight_value,
    oi.price + oi.freight_value   AS total_value
FROM clean.order_items oi
JOIN clean.orders o            USING (order_id)
LEFT JOIN clean.customers c    USING (customer_id)
LEFT JOIN mart.dim_customer dc ON dc.customer_unique_id = c.customer_unique_id  -- customer_id -> NGƯỜI
LEFT JOIN mart.dim_product dp  ON dp.product_id = oi.product_id
LEFT JOIN mart.dim_seller ds   ON ds.seller_id  = oi.seller_id;
