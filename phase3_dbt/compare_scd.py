"""
So sánh SCD Type 1 (ghi đè) và SCD Type 2 (giữ lịch sử) sau khi 500 khách chuyển SP → RJ.

Chạy:  .venv/Scripts/python phase3_dbt/compare_scd.py
"""
import os
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
con = duckdb.connect(str(Path(os.getenv("ELT_WAREHOUSE_PATH", ROOT / "warehouse" / "shoplens_elt.duckdb"))),
                     read_only=True)


def show(title: str, sql: str) -> None:
    print(f"\n=== {title} ===")
    con.sql(sql).show(max_width=160)


show("Số người có nhiều hơn 1 phiên bản địa chỉ trong dim_customer", """
    SELECT COUNT(*) AS so_nguoi_co_lich_su
    FROM (SELECT customer_unique_id FROM marts.dim_customer GROUP BY 1 HAVING COUNT(*) > 1)""")

show("Lịch sử của 1 người đã chuyển nhà (SCD2: 2 dòng, mỗi dòng 1 khoảng hiệu lực)", """
    WITH one AS (SELECT customer_unique_id FROM marts.dim_customer
                 GROUP BY 1 HAVING COUNT(*) > 1 ORDER BY 1 LIMIT 1)
    SELECT left(customer_key, 10) || '…' AS customer_key, city, state,
           valid_from::TIMESTAMP(0) AS valid_from, valid_to::TIMESTAMP(0) AS valid_to, is_current
    FROM marts.dim_customer JOIN one USING (customer_unique_id)
    ORDER BY valid_from""")

show("Doanh thu LỊCH SỬ (2016-2018) theo bang: SCD1 vs SCD2", """
    WITH scd2 AS (    -- gắn đơn với địa chỉ ĐANG HIỆU LỰC LÚC MUA (đúng)
        SELECT c.state, SUM(f.price) AS revenue
        FROM marts.fact_order_items f JOIN marts.dim_customer c USING (customer_key)
        GROUP BY 1
    ),
    scd1 AS (         -- gắn đơn với địa chỉ HIỆN TẠI (như phase 2: ghi đè)
        SELECT cur.state, SUM(f.price) AS revenue
        FROM marts.fact_order_items f
        JOIN marts.dim_customer v   USING (customer_key)
        JOIN marts.dim_customer cur ON cur.customer_unique_id = v.customer_unique_id AND cur.is_current
        GROUP BY 1
    )
    SELECT state,
           ROUND(scd1.revenue, 0) AS scd1_dia_chi_hien_tai,
           ROUND(scd2.revenue, 0) AS scd2_dia_chi_luc_mua,
           ROUND(scd1.revenue - scd2.revenue, 0) AS chenh_lech
    FROM scd1 JOIN scd2 USING (state)
    WHERE state IN ('SP', 'RJ')
    ORDER BY state DESC""")

print("""
→ SCD1: 500 người chuyển đi kéo theo TOÀN BỘ doanh thu cũ của họ sang RJ, lịch sử bị viết lại.
→ SCD2: đơn cũ vẫn tính cho SP (nơi họ ở lúc mua). Đơn mới (nếu có) sẽ tính cho RJ.
  Cả hai đều "đúng", tuỳ câu hỏi: "khách hiện ở đâu?" (SCD1) hay "bán được bao nhiêu ở đâu?" (SCD2).""")
