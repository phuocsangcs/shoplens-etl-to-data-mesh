"""
Phase 2: Dựng star schema (schema `mart`) từ dữ liệu đã làm sạch (schema `clean`, phase 1).

Chạy:  .venv/Scripts/python phase2_star_schema/build_star.py
(Yêu cầu đã chạy phase 1 pipeline trước.)

Luồng:  clean.* ──(SQL trong sql/*.sql, chạy theo thứ tự tên file)──▶ mart.dim_* + mart.fact_*
        rồi chạy bộ KIỂM TRA: grain đúng chưa, khoá có "mồ côi" không, tổng tiền có khớp nguồn không.

Lưu ý: mart được dựng lại TOÀN BỘ mỗi lần (CREATE OR REPLACE). Ở quy mô 100k đơn thì mất vài giây,
đơn giản và luôn idempotent. Ở quy mô lớn sẽ cần build incremental (phase 3 với dbt).
"""
import os
import time
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
WAREHOUSE_PATH = Path(os.getenv("WAREHOUSE_PATH", ROOT / "warehouse" / "shoplens.duckdb"))
SQL_DIR = Path(__file__).parent / "sql"

# Mỗi kiểm tra là một câu SQL trả về MỘT con số. Con số đó PHẢI = 0 thì mới đạt.
CHECKS = {
    # 1. GRAIN: khoá của grain phải duy nhất
    "grain fact_order_items (order_id, order_item_id) duy nhất":
        "SELECT COUNT(*) - COUNT(DISTINCT (order_id, order_item_id)) FROM mart.fact_order_items",
    "grain fact_payments (order_id, payment_sequential) duy nhất":
        "SELECT COUNT(*) - COUNT(DISTINCT (order_id, payment_sequential)) FROM mart.fact_payments",
    "grain fact_orders (order_id) duy nhất":
        "SELECT COUNT(*) - COUNT(DISTINCT order_id) FROM mart.fact_orders",
    "dim_customer: mỗi người 1 dòng":
        "SELECT COUNT(*) - COUNT(DISTINCT customer_unique_id) FROM mart.dim_customer",
    # 2. TOÀN VẸN THAM CHIẾU: mọi khoá trong fact phải có trong dim
    "fact_order_items.product_key đều có trong dim_product":
        "SELECT COUNT(*) FROM mart.fact_order_items f ANTI JOIN mart.dim_product d USING (product_key)",
    "fact_order_items.order_date_key đều có trong dim_date":
        "SELECT COUNT(*) FROM mart.fact_order_items f ANTI JOIN mart.dim_date d ON d.date_key = f.order_date_key",
    "fact_orders.customer_key đều có trong dim_customer":
        "SELECT COUNT(*) FROM mart.fact_orders f ANTI JOIN mart.dim_customer d USING (customer_key)",
    # 3. ĐỐI SOÁT (reconciliation): mart phải khớp nguồn, không mất / không thừa đồng nào
    "tổng price: fact_order_items = clean.order_items":
        "SELECT ROUND((SELECT SUM(price) FROM mart.fact_order_items) - (SELECT SUM(price) FROM clean.order_items), 2)",
    "tổng tiền thanh toán: fact_payments = clean.order_payments":
        "SELECT ROUND((SELECT SUM(payment_value) FROM mart.fact_payments) - (SELECT SUM(payment_value) FROM clean.order_payments), 2)",
    "số đơn: fact_orders = clean.orders":
        "SELECT (SELECT COUNT(*) FROM mart.fact_orders) - (SELECT COUNT(*) FROM clean.orders)",
}


def main():
    con = duckdb.connect(str(WAREHOUSE_PATH))
    con.execute("CREATE SCHEMA IF NOT EXISTS mart")

    print("Dựng star schema:")
    con.execute("BEGIN TRANSACTION")
    for sql_file in sorted(SQL_DIR.glob("*.sql")):
        t0 = time.perf_counter()
        con.execute(sql_file.read_text(encoding="utf-8"))
        print(f"  ✓ {sql_file.name:<28} ({time.perf_counter() - t0:.2f}s)")
    con.execute("COMMIT")

    print("\nSố dòng:")
    for (schema, table) in con.execute("""
            SELECT schema_name, table_name FROM duckdb_tables()
            WHERE schema_name IN ('mart', 'mart_snowflake') ORDER BY schema_name, table_name""").fetchall():
        n = con.execute(f"SELECT COUNT(*) FROM {schema}.{table}").fetchone()[0]
        print(f"  {schema + '.' + table:<32} {n:>9,}")

    print("\nKiểm tra chất lượng mô hình (phải = 0):")
    failed = 0
    for name, sql in CHECKS.items():
        value = con.execute(sql).fetchone()[0] or 0
        ok = value == 0
        failed += not ok
        print(f"  {'✅' if ok else '❌'} {name:<62} = {value}")
    con.close()

    if failed:
        raise SystemExit(f"\n{failed} kiểm tra thất bại!")
    print("\nTất cả kiểm tra đạt.")


if __name__ == "__main__":
    main()
