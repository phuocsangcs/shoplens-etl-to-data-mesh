"""
Phase 2: Trả lời câu hỏi business trên star schema. So sánh với "nỗi đau" phase 0.

Chạy:  .venv/Scripts/python phase2_star_schema/analyze.py

Để ý HÌNH DẠNG của mọi query bên dưới: luôn là
    SELECT <cột của dim>, <hàm tổng hợp measure của fact>
    FROM fact JOIN dim ... GROUP BY <cột của dim>
Đó là "star join": fact ở giữa, dim xung quanh, mỗi dim cách fact đúng 1 JOIN.
"""
import os
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
con = duckdb.connect(str(Path(os.getenv("WAREHOUSE_PATH", ROOT / "warehouse" / "shoplens.duckdb"))), read_only=True)


def ask(title: str, sql: str) -> None:
    print(f"\n=== {title} ===")
    con.sql(sql).show(max_width=150)


# ---------------------------------------------------------------- nỗi đau #2: bẫy customer_id
ask("[#2 đã diệt] Tỉ lệ khách quay lại: 1 bảng, 0 JOIN (phase 0: 3.12%)", """
    SELECT COUNT(*) AS so_nguoi,
           ROUND(100.0 * AVG(is_repeat_customer::INT), 2) AS pct_khach_quay_lai
    FROM mart.dim_customer WHERE customer_key <> -1""")

# ---------------------------------------------------------------- nỗi đau #3: fan-out
ask("[#3 đã diệt] Doanh thu đơn đã giao (phase 0, cách đúng: 13,221,498.11)", """
    SELECT ROUND(SUM(price), 2) AS doanh_thu_brl
    FROM mart.fact_order_items WHERE order_status = 'delivered'""")

ask("[#3] Doanh thu theo PHƯƠNG THỨC THANH TOÁN: dùng fact_payments (grain khác!)", """
    SELECT payment_type,
           COUNT(DISTINCT order_id)                    AS so_don,
           ROUND(SUM(payment_value), 0)                AS tien_thu_brl,
           ROUND(AVG(payment_installments), 1)         AS tra_gop_tb_ky
    FROM mart.fact_payments
    GROUP BY 1 ORDER BY 3 DESC""")

# ---------------------------------------------------------------- star join điển hình
ask("Doanh thu theo QUÝ × CATEGORY (top 3 mỗi quý, 2018): fact + 2 dim", """
    SELECT d.year || '-Q' || d.quarter AS quy, p.category,
           ROUND(SUM(f.price), 0) AS doanh_thu_brl
    FROM mart.fact_order_items f
    JOIN mart.dim_date d    ON d.date_key = f.order_date_key
    JOIN mart.dim_product p USING (product_key)
    WHERE f.order_status = 'delivered' AND d.year = 2018
    GROUP BY 1, 2
    QUALIFY ROW_NUMBER() OVER (PARTITION BY quy ORDER BY doanh_thu_brl DESC) <= 3
    ORDER BY quy, doanh_thu_brl DESC""")

ask("Black Friday vs ngày thường (2017): nhờ cột is_black_friday có sẵn trong dim_date", """
    SELECT CASE WHEN d.is_black_friday THEN 'Black Friday' ELSE 'ngày thường (TB)' END AS loai_ngay,
           ROUND(COUNT(DISTINCT f.order_id) / COUNT(DISTINCT d.date_key), 0) AS don_moi_ngay
    FROM mart.fact_order_items f
    JOIN mart.dim_date d ON d.date_key = f.order_date_key
    WHERE d.year = 2017
    GROUP BY 1""")

# ---------------------------------------------------------------- fact_orders: logistics
ask("Giao TRỄ ảnh hưởng thế nào tới điểm review? (fact_orders)", """
    SELECT CASE WHEN is_late THEN 'giao trễ' ELSE 'đúng hạn' END AS giao_hang,
           COUNT(*)                         AS so_don,
           ROUND(AVG(delivery_days), 1)     AS ngay_giao_tb,
           ROUND(AVG(review_score), 2)      AS diem_review_tb,
           ROUND(100.0 * AVG((review_score <= 2)::INT), 1) AS pct_review_1_2_sao
    FROM mart.fact_orders
    WHERE order_status = 'delivered' AND is_late IS NOT NULL
    GROUP BY 1""")

ask("Bang (state) nào bị giao trễ nhiều nhất? fact_orders + dim_customer", """
    SELECT c.state,
           COUNT(*) AS so_don,
           ROUND(100.0 * AVG(f.is_late::INT), 1) AS pct_tre,
           ROUND(AVG(f.delivery_days), 1)        AS ngay_giao_tb
    FROM mart.fact_orders f
    JOIN mart.dim_customer c USING (customer_key)
    WHERE f.is_late IS NOT NULL
    GROUP BY 1 HAVING COUNT(*) > 500
    ORDER BY pct_tre DESC LIMIT 6""")

# ---------------------------------------------------------------- star vs snowflake
ask("STAR: doanh thu theo category = fact + 1 JOIN", """
    SELECT p.category, ROUND(SUM(f.price), 0) AS doanh_thu
    FROM mart.fact_order_items f
    JOIN mart.dim_product p USING (product_key)
    GROUP BY 1 ORDER BY 2 DESC LIMIT 3""")

ask("SNOWFLAKE: cùng câu hỏi = fact + 2 JOIN (kết quả y hệt)", """
    SELECT c.category, ROUND(SUM(f.price), 0) AS doanh_thu
    FROM mart.fact_order_items f
    JOIN mart_snowflake.dim_product p  USING (product_key)
    JOIN mart_snowflake.dim_category c USING (category_key)
    GROUP BY 1 ORDER BY 2 DESC LIMIT 3""")
