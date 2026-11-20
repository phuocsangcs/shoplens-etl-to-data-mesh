"""
Soi warehouse sau khi chạy ETL: nhật ký chạy, watermark, và so sánh "nỗi đau" phase 0
trên dữ liệu ĐÃ LÀM SẠCH.

Chạy:  .venv/Scripts/python phase1_python_etl/inspect_warehouse.py
"""
import duckdb

import config


def show(con, title: str, sql: str) -> None:
    print(f"\n=== {title} ===")
    con.sql(sql).show(max_width=140)


con = duckdb.connect(str(config.WAREHOUSE_PATH), read_only=True)

show(con, "Nhật ký chạy (bảng orders)", """
    SELECT run_id, mode, as_of::DATE AS as_of, rows_extracted, rows_loaded, finished_at::TIMESTAMP(0) AS finished_at
    FROM etl_meta.run_log WHERE table_name = 'orders' ORDER BY finished_at""")

show(con, "Watermark hiện tại", "SELECT * FROM etl_meta.watermarks")

show(con, "Kiểm tra: khoá có bị trùng sau nhiều lần chạy? (phải = 0)", """
    SELECT 'orders'      AS bang, COUNT(*) - COUNT(DISTINCT order_id) AS so_dong_trung FROM clean.orders
    UNION ALL SELECT 'order_items',   COUNT(*) - COUNT(DISTINCT (order_id, order_item_id)) FROM clean.order_items
    UNION ALL SELECT 'order_reviews', COUNT(*) - COUNT(DISTINCT order_id) FROM clean.order_reviews""")

show(con, "Nỗi đau #1a đã đỡ: tên São Paulo sau chuẩn hoá", """
    SELECT city, COUNT(*) AS so_zip FROM clean.geolocation
    WHERE state = 'SP' AND city LIKE '%sao%paulo%' OR city = 'saopaulo'
    GROUP BY 1 ORDER BY 2 DESC""")

show(con, "Nỗi đau #1b đã đỡ: category NULL / chưa dịch (phải = 0)", """
    SELECT COUNT(*) FILTER (WHERE product_category_name IS NULL)         AS null_category,
           COUNT(*) FILTER (WHERE product_category_name_english IS NULL) AS chua_dich,
           COUNT(*) FILTER (WHERE product_category_name = 'unknown')     AS gan_nhan_unknown
    FROM clean.products""")

show(con, "Nỗi đau #4 đã đỡ: top category 2018, từ 4 JOIN còn 2 JOIN, không còn COALESCE", """
    SELECT p.product_category_name_english AS category,
           COUNT(DISTINCT o.order_id) AS so_don, ROUND(SUM(oi.price), 2) AS doanh_thu_brl
    FROM clean.orders o
    JOIN clean.order_items oi USING (order_id)
    JOIN clean.products p     USING (product_id)
    WHERE o.order_status = 'delivered' AND o.order_purchase_timestamp >= '2018-01-01'
    GROUP BY 1 ORDER BY 3 DESC LIMIT 5""")

show(con, "Cờ chất lượng (không xoá, chỉ đánh dấu)", """
    SELECT COUNT(*) FILTER (WHERE NOT has_items)           AS don_khong_co_mon,
           COUNT(*) FILTER (WHERE is_delivered_missing_date) AS delivered_thieu_ngay
    FROM clean.orders""")

print("\n⚠️  Vẫn còn: bẫy customer_id (#2), fan-out (#3), mất lịch sử. Làm sạch chưa đủ, cần MÔ HÌNH HOÁ (phase 2).")
