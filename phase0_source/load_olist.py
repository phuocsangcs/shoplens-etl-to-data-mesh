"""
Phase 0: Nạp 9 file CSV của Olist (Kaggle) vào Postgres, để Postgres đóng vai
"DB production của sàn thương mại điện tử" (hệ thống OLTP).

Chạy:  .venv/Scripts/python phase0_source/load_olist.py

Lưu ý: bước này KHÔNG phải ETL. Đây chỉ là dựng lại "thế giới thật" (app DB đang chạy)
để các phase sau có một nguồn để Extract.
"""
import os
import time
from pathlib import Path

import psycopg

SOURCE_DB_URL = os.getenv("SOURCE_DB_URL", "postgresql://shop:shop@localhost:5440/shop")

ROOT = Path(__file__).resolve().parent.parent
CSV_DIR = ROOT / "data" / "raw" / "olist"

# Thứ tự quan trọng: bảng cha trước, bảng con sau (vì có khoá ngoại)
FILES = [
    ("product_category_name_translation", "product_category_name_translation.csv"),
    ("customers",      "olist_customers_dataset.csv"),
    ("sellers",        "olist_sellers_dataset.csv"),
    ("products",       "olist_products_dataset.csv"),
    ("orders",         "olist_orders_dataset.csv"),
    ("order_items",    "olist_order_items_dataset.csv"),
    ("order_payments", "olist_order_payments_dataset.csv"),
    ("order_reviews",  "olist_order_reviews_dataset.csv"),
    ("geolocation",    "olist_geolocation_dataset.csv"),
]


def copy_csv(cur, table: str, path: Path) -> int:
    """
    Dùng lệnh COPY của Postgres: stream file thẳng vào bảng, nhanh hơn INSERT từng dòng
    hàng trăm lần. Parser CSV của Postgres tự xử lý dấu ngoặc kép và xuống dòng trong ô.
    encoding='utf-8-sig' để bỏ ký tự BOM ở đầu file translation.
    """
    with open(path, encoding="utf-8-sig") as f:
        header = f.readline().strip()  # dùng header của file làm danh sách cột
        columns = header.replace('"', "")
        with cur.copy(f"COPY {table} ({columns}) FROM STDIN WITH (FORMAT csv)") as cp:
            while chunk := f.read(1024 * 1024):
                cp.write(chunk)
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    return cur.fetchone()[0]


def main():
    missing = [f for _, f in FILES if not (CSV_DIR / f).exists()]
    if missing:
        raise SystemExit(f"Thiếu file trong {CSV_DIR}: {missing}")

    schema_sql = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")
    with psycopg.connect(SOURCE_DB_URL) as conn, conn.cursor() as cur:
        cur.execute(schema_sql)  # xoá & tạo lại -> chạy lại bao nhiêu lần cũng được
        print("Nạp CSV vào Postgres (DB nguồn):")
        for table, filename in FILES:
            t0 = time.perf_counter()
            n = copy_csv(cur, table, CSV_DIR / filename)
            print(f"  {table:<34} {n:>9,} dòng  ({time.perf_counter() - t0:.1f}s)")
        cur.execute("ANALYZE")  # cập nhật thống kê cho query planner


if __name__ == "__main__":
    main()
