"""
SELF-SERVE PLATFORM: công cụ ingest dùng chung cho MỌI domain.

Domain không cần biết cách kết nối Postgres hay copy data. Chỉ cần viết file
domains/<domain>/ingest.yml khai báo "tôi cần bảng nào, cột nào", rồi gọi:

    .venv/Scripts/python phase6_data_mesh/platform/ingest.py --domain sales

Mỗi domain có warehouse RIÊNG: warehouse/mesh/<domain>.duckdb (schema raw).
"""
import argparse
import os
import time
from pathlib import Path

import duckdb
import yaml

MESH_DIR = Path(__file__).resolve().parent.parent
ROOT = MESH_DIR.parent
WAREHOUSE_DIR = ROOT / "warehouse" / "mesh"
SOURCE_DSN = os.getenv("SOURCE_DSN", "host=localhost port=5440 dbname=shop user=shop password=shop")


def ingest(domain: str) -> dict[str, int]:
    config = yaml.safe_load((MESH_DIR / "domains" / domain / "ingest.yml").read_text(encoding="utf-8"))
    WAREHOUSE_DIR.mkdir(parents=True, exist_ok=True)
    db_path = WAREHOUSE_DIR / f"{domain}.duckdb"

    counts = {}
    with duckdb.connect(str(db_path)) as con:
        con.execute("INSTALL postgres; LOAD postgres;")
        con.execute(f"ATTACH '{SOURCE_DSN}' AS src (TYPE postgres, READ_ONLY)")
        con.execute("CREATE SCHEMA IF NOT EXISTS raw")
        print(f"[platform.ingest] domain={domain} → {db_path.relative_to(ROOT)}")
        for table, columns in config["tables"].items():
            t0 = time.perf_counter()
            cols = ", ".join(columns)  # chỉ lấy đúng các cột domain sở hữu
            con.execute(f"CREATE OR REPLACE TABLE raw.{table} AS "
                        f"SELECT {cols}, now() AS _loaded_at FROM src.public.{table}")
            counts[table] = con.execute(f"SELECT COUNT(*) FROM raw.{table}").fetchone()[0]
            print(f"  raw.{table:<16} {len(columns):>2} cột  {counts[table]:>8,} dòng  ({time.perf_counter() - t0:.1f}s)")
    return counts


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--domain", required=True)
    ingest(p.parse_args().domain)
