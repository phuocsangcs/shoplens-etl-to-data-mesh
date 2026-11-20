-- =====================================================================
-- FACT: fact_payments
-- GRAIN: mỗi dòng = 1 LẦN THANH TOÁN của 1 đơn.
-- Trả lời câu hỏi về TIỀN THU (theo phương thức, trả góp), khác với fact_order_items (về HÀNG BÁN).
-- =====================================================================
CREATE OR REPLACE TABLE mart.fact_payments AS
SELECT
    p.order_id,
    p.payment_sequential,
    CAST(strftime(o.order_purchase_timestamp, '%Y%m%d') AS INTEGER) AS order_date_key,
    COALESCE(dc.customer_key, -1) AS customer_key,
    p.payment_type,
    p.payment_installments,
    p.payment_value
FROM clean.order_payments p
JOIN clean.orders o            USING (order_id)
LEFT JOIN clean.customers c    USING (customer_id)
LEFT JOIN mart.dim_customer dc ON dc.customer_unique_id = c.customer_unique_id;
