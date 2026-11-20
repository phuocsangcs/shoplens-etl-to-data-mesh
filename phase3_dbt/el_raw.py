"""
Phase 3 - bước "EL" của ELT: Extract + Load NGUYÊN TRẠNG vào warehouse, KHÔNG transform gì.

Chạy:  .venv/Scripts/python phase3_dbt/el_raw.py

So với phase 1:
  - Phase 1 (ETL): Postgres → pandas làm sạch → warehouse. Data thô bị bỏ, chỉ giữ bản đã sạch.
  - Phase 3 (ELT): Postgres → warehouse schema `raw` y nguyên bản. Làm sạch để dbt lo, bằng SQL.
    -> Data thô luôn còn đó. Quy tắc đổi thì chỉ cần chạy lại dbt, không phải extract lại nguồn.

Ở công ty thật, bước này thường do tool chuyên dụng làm (Airbyte, Fivetran, dlt...).
Ở đây DuckDB tự "ATTACH" Postgres và copy thẳng, gọn như một tool EL mini.
"""
import os
import time
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
WAREHOUSE_PATH = Path(os.getenv("ELT_WAREHOUSE_PATH", ROOT / "warehouse" / "shoplens_elt.duckdb"))
SOURCE_DSN = os.getenv("SOURCE_DSN", "host=localhost port=5440 dbname=shop user=shop password=shop")

TABLES = ["customers", "sellers", "products", "product_category_name_translation",
          "orders", "order_items", "order_payments", "order_reviews", "geolocation"]


def main():
    WAREHOUSE_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(WAREHOUSE_PATH))
    con.execute("INSTALL postgres; LOAD postgres;")
    con.execute(f"ATTACH '{SOURCE_DSN}' AS src (TYPE postgres, READ_ONLY)")  # chỉ đọc nguồn
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")

    print(f"EL: Postgres → {WAREHOUSE_PATH.name} (schema raw)")
    for t in TABLES:
        t0 = time.perf_counter()
        # Copy y nguyên + 1 cột metadata: lúc nào dòng này được nạp (phục vụ kiểm tra freshness)
        con.execute(f"""
            CREATE OR REPLACE TABLE raw.{t} AS
            SELECT *, now() AS _loaded_at FROM src.public.{t}
        """)
        n = con.execute(f"SELECT COUNT(*) FROM raw.{t}").fetchone()[0]
        print(f"  raw.{t:<36} {n:>9,} dòng  ({time.perf_counter() - t0:.1f}s)")
    con.close()


if __name__ == "__main__":
    main()
