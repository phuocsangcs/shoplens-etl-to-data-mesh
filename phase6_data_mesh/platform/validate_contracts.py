"""
FEDERATED COMPUTATIONAL GOVERNANCE: kiểm tra TỰ ĐỘNG mọi data product theo luật chung (policies.yml).

Chạy:  .venv/Scripts/python phase6_data_mesh/platform/validate_contracts.py
Thoát với mã 1 nếu có vi phạm, để gắn vào CI hoặc orchestrator: vi phạm thì chặn lại.

Kiểm tra cho mỗi domain:
  1. Contract đủ trường bắt buộc (owner, version, SLA...)
  2. Đặt tên đúng luật: schema `output`, tên bảng có hậu tố _v<version>
  3. Bảng THẬT khớp contract: đúng tên cột, đúng kiểu, không thừa không thiếu
  4. Khoá chính unique + not null
  5. Freshness: dữ liệu không cũ hơn SLA đã hứa
  6. Consumption: domain chỉ đọc domain khác qua output port, và chỉ đọc data product có thật
"""
import sys
from datetime import datetime

import yaml

from mesh_lib import DOMAINS_DIR, load_contracts, load_policies, open_output_port, split_table


class Report:
    def __init__(self):
        self.failures = 0

    def check(self, ok: bool, label: str, detail: str = "") -> None:
        self.failures += not ok
        print(f"    {'✅' if ok else '❌'} {label}" + (f": {detail}" if detail else ""))


def validate_domain(domain: str, c: dict, policies: dict, all_contracts: dict, r: Report) -> None:
    print(f"\n■ {domain}: {c.get('name')} v{c.get('version')}")

    # 1. Trường bắt buộc
    missing = [f for f in policies["required_fields"] if f not in c]
    r.check(not missing, "contract đủ trường bắt buộc", f"thiếu {missing}" if missing else "")
    if missing:
        return

    # 2. Quy ước đặt tên output port
    schema, table = split_table(c)
    suffix = policies["output_port"]["table_suffix_pattern"].format(version=c["version"])
    r.check(schema == policies["output_port"]["schema"], f"output port nằm trong schema '{policies['output_port']['schema']}'", schema)
    r.check(table.endswith(suffix), f"tên bảng có hậu tố {suffix}", table)

    # 3. Schema thật vs contract
    declared = {col["name"]: col["type"].upper() for col in c["schema"]}
    bad_types = [n for n, t in declared.items() if t not in policies["columns"]["allowed_types"]]
    r.check(not bad_types, "kiểu dữ liệu nằm trong danh sách cho phép", f"{bad_types}" if bad_types else "")
    req_cols = [x for x in policies["columns"]["required"] if x not in declared]
    r.check(not req_cols, f"có cột bắt buộc {policies['columns']['required']}", f"thiếu {req_cols}" if req_cols else "")

    with open_output_port(c) as con:
        actual = {name: dtype.upper() for name, dtype in con.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = ? AND table_name = ?", [schema, table]).fetchall()}
        if not actual:
            r.check(False, "bảng output tồn tại", f"{schema}.{table} không có")
            return
        extra = sorted(set(actual) - set(declared))
        absent = sorted(set(declared) - set(actual))
        wrong = sorted(n for n in set(declared) & set(actual) if declared[n] != actual[n])
        problems = (([f"thiếu {absent}"] if absent else []) + ([f"thừa {extra}"] if extra else [])
                    + ([f"sai kiểu {[(n, actual[n], declared[n]) for n in wrong]}"] if wrong else []))
        r.check(not problems, f"bảng thật khớp contract ({len(declared)} cột)", "; ".join(problems))

        # 4. Khoá chính
        pk = c["primary_key"]
        total, distinct, nulls = con.execute(
            f"SELECT COUNT(*), COUNT(DISTINCT {pk}), COUNT(*) - COUNT({pk}) FROM {schema}.{table}").fetchone()
        r.check(total == distinct and nulls == 0, f"khoá chính '{pk}' unique & not null",
                f"{total:,} dòng, {total - distinct} trùng, {nulls} null")

        # 5. Freshness
        published = con.execute(f"SELECT MAX(_published_at) FROM {schema}.{table}").fetchone()[0]
    age_h = (datetime.now() - published).total_seconds() / 3600
    sla = c["sla"]["max_age_hours"]
    r.check(sla <= policies["sla"]["max_age_hours_limit"], f"SLA {sla}h không vượt trần {policies['sla']['max_age_hours_limit']}h")
    r.check(age_h <= sla, f"freshness trong SLA {sla}h", f"xuất bản {age_h:.1f} giờ trước")

    # 6. Consumption: domain này đọc domain khác thế nào? (đọc khai báo source trong dbt project)
    products_by_table = {cc["output_port"]["table"].split(".")[1]: cc for cc in all_contracts.values()}
    for src_file in (DOMAINS_DIR / domain / "dbt" / "models").rglob("_sources.yml"):
        for src in yaml.safe_load(src_file.read_text(encoding="utf-8")).get("sources", []):
            if "database" not in src:  # source nội bộ của chính domain
                continue
            for t in src.get("tables", []):
                ref = f"{src['database']}.{src['schema']}.{t['name']}"
                allowed = policies["consumption"]["allowed_foreign_schema"]
                r.check(src["schema"] == allowed, f"đọc domain khác qua output port: {ref}",
                        "" if src["schema"] == allowed else f"vi phạm, chỉ được đọc schema '{allowed}'")
                producer = products_by_table.get(t["name"])
                r.check(producer is not None, f"'{t['name']}' là data product đã đăng ký",
                        producer["name"] if producer else "không có trong catalog")
                if producer:
                    listed = c["name"] in producer.get("consumers", [])
                    r.check(listed, f"đã đăng ký là consumer của {producer['name']}",
                            "" if listed else "producer không biết bạn đang dùng, sẽ không được báo khi đổi")


def main() -> int:
    policies = load_policies()
    contracts = load_contracts()
    print(f"GOVERNANCE CHECK: {len(contracts)} data product, luật trong platform/policies.yml")
    r = Report()
    for domain, c in contracts.items():
        validate_domain(domain, c, policies, contracts, r)
    print(f"\n{'✅ Tất cả đạt' if r.failures == 0 else f'❌ {r.failures} vi phạm'}")
    return 1 if r.failures else 0


if __name__ == "__main__":
    sys.exit(main())
