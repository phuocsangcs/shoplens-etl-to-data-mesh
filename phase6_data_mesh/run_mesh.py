"""
Chạy toàn bộ mesh từ đầu đến cuối (mô phỏng một "ngày làm việc" của các domain).

Chạy:  .venv/Scripts/python phase6_data_mesh/run_mesh.py

Ngoài đời, MỖI domain tự lập lịch pipeline của mình (vd: mỗi team một Dagster project như phase 4):
Sales chạy 02:00, Logistics chạy 03:00 vì phụ thuộc sales.orders. Script này gom lại cho tiện demo.
Bước nào lỗi thì dừng ngay, không chạy các bước sau.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

MESH = Path(__file__).resolve().parent
ROOT = MESH.parent
PY = sys.executable
DBT = str(Path(sys.executable).parent / "dbt")
ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}

STEPS = [
    ("[sales]     platform ingest",      [PY, "platform/ingest.py", "--domain", "sales"], MESH),
    ("[sales]     dbt deps + build",     [DBT, "deps"], MESH / "domains/sales/dbt"),
    (None,                               [DBT, "build"], MESH / "domains/sales/dbt"),
    ("[logistics] platform ingest",      [PY, "platform/ingest.py", "--domain", "logistics"], MESH),
    ("[logistics] dbt deps + build",     [DBT, "deps"], MESH / "domains/logistics/dbt"),
    (None,                               [DBT, "build"], MESH / "domains/logistics/dbt"),
    ("[platform]  governance check",     [PY, "platform/validate_contracts.py"], MESH),
    ("[platform]  catalog",              [PY, "platform/catalog.py"], MESH),
    ("[consumer]  exec report",          [PY, "consumers/exec_report.py"], MESH),
]


def main():
    t_all = time.perf_counter()
    for title, cmd, cwd in STEPS:
        if title:
            print(f"\n{'=' * 70}\n▶ {title}\n{'=' * 70}")
        t0 = time.perf_counter()
        res = subprocess.run(cmd, cwd=cwd, env=ENV, capture_output=True, text=True, encoding="utf-8")
        out = res.stdout
        if cmd[0] == DBT:  # dbt in rất nhiều; chỉ giữ dòng tổng kết
            out = "\n".join(l for l in out.splitlines() if "Done." in l or "ERROR" in l or "Installed" in l)
        print(out.rstrip())
        if res.returncode != 0:
            print(res.stderr[-2000:])
            sys.exit(f"\n✖ Dừng: bước '{' '.join(Path(c).name for c in cmd[:2])}' lỗi (exit {res.returncode})")
        print(f"   ({time.perf_counter() - t0:.1f}s)")
    print(f"\n✔ Mesh chạy xong sau {time.perf_counter() - t_all:.0f}s")


if __name__ == "__main__":
    main()
