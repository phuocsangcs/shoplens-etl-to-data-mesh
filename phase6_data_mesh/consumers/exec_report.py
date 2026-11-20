"""
CONSUMER: báo cáo cho ban giám đốc, dùng data product của CẢ HAI domain.

Chạy:  .venv/Scripts/python phase6_data_mesh/consumers/exec_report.py

Consumer không cần warehouse trung tâm, không cần biết bảng nội bộ của ai. Chỉ cần mở
output port (read-only) của các data product mình đã đăng ký và JOIN theo order_id.
"""
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
MESH = ROOT / "warehouse" / "mesh"

con = duckdb.connect()  # DB tạm trong RAM, chỉ để JOIN
con.execute(f"ATTACH '{MESH / 'sales.duckdb'}' AS sales (READ_ONLY)")
con.execute(f"ATTACH '{MESH / 'logistics.duckdb'}' AS logistics (READ_ONLY)")


def show(title: str, sql: str) -> None:
    print(f"\n=== {title} ===")
    con.sql(sql).show(max_width=150)


show("[sales.orders_v1] Doanh thu đơn đã giao (phase 2: 13,221,498.11)", """
    SELECT ROUND(SUM(items_value), 2) AS doanh_thu_brl, COUNT(*) AS so_don
    FROM sales.output.orders_v1 WHERE order_status = 'delivered'""")

show("[logistics.delivery_performance_v1] Giao trễ ảnh hưởng review (phase 2: 4.29 vs 2.27)", """
    SELECT CASE WHEN is_late THEN 'giao trễ' ELSE 'đúng hạn' END AS giao_hang,
           COUNT(*) AS so_don,
           ROUND(AVG(delivery_days), 1) AS ngay_giao_tb,
           ROUND(AVG(review_score), 2)  AS diem_review_tb
    FROM logistics.output.delivery_performance_v1
    GROUP BY 1 ORDER BY 1 DESC""")

show("[logistics] Giao liên bang vs nội bang", """
    SELECT CASE WHEN is_interstate THEN 'liên bang' ELSE 'nội bang' END AS loai,
           COUNT(*) AS so_don,
           ROUND(AVG(delivery_days), 1) AS ngay_giao_tb,
           ROUND(100.0 * AVG(is_late::INT), 1) AS pct_tre
    FROM logistics.output.delivery_performance_v1
    WHERE is_interstate IS NOT NULL
    GROUP BY 1""")

show("[JOIN 2 domain] Bang nào vừa mang doanh thu lớn vừa hay giao trễ?", """
    SELECT s.customer_state                       AS bang,
           ROUND(SUM(s.items_value), 0)           AS doanh_thu_brl,
           ROUND(100.0 * AVG(l.is_late::INT), 1)  AS pct_tre,
           ROUND(AVG(l.review_score), 2)          AS review_tb
    FROM sales.output.orders_v1 s
    JOIN logistics.output.delivery_performance_v1 l USING (order_id)
    GROUP BY 1
    ORDER BY doanh_thu_brl DESC
    LIMIT 6""")
