"""
DATA CATALOG: "trang vàng" của mesh. Ai cũng tra được: có data product nào, của ai,
ở đâu, tươi tới đâu, ai đang dùng. (Nguyên tắc "discoverable" của data product.)

Chạy:  .venv/Scripts/python phase6_data_mesh/platform/catalog.py
Ngoài đời: DataHub, OpenMetadata, Atlan, Unity Catalog... làm việc này ở quy mô lớn.
"""
from datetime import datetime

from mesh_lib import load_contracts, open_output_port, split_table


def main():
    contracts = load_contracts()
    print(f"DATA PRODUCT CATALOG ({len(contracts)} sản phẩm)\n")
    for domain, c in contracts.items():
        schema, table = split_table(c)
        with open_output_port(c) as con:
            rows, published = con.execute(
                f"SELECT COUNT(*), MAX(_published_at) FROM {schema}.{table}").fetchone()
        age_h = (datetime.now() - published).total_seconds() / 3600
        inputs = [p.get("data_product") for p in c.get("input_ports", []) if p.get("data_product")]
        print(f"■ {c['name']}  (v{c['version']})   domain: {domain}")
        print(f"    owner      : {c['owner']['team']} <{c['owner']['contact']}>")
        print(f"    mô tả      : {' '.join(c['description'].split())}")
        print(f"    output port: {c['output_port']['warehouse']} → {c['output_port']['table']}")
        print(f"    quy mô     : {rows:,} dòng, {len(c['schema'])} cột, khoá chính: {c['primary_key']}")
        print(f"    freshness  : xuất bản {published:%Y-%m-%d %H:%M} ({age_h:.1f} giờ trước), SLA ≤ {c['sla']['max_age_hours']}h")
        print(f"    phụ thuộc  : {', '.join(inputs) or '(chỉ dữ liệu của chính domain)'}")
        print(f"    consumers  : {', '.join(c.get('consumers', [])) or '-'}\n")


if __name__ == "__main__":
    main()
