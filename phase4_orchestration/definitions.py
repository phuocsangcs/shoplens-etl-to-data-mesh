"""
Phase 4: Orchestration với Dagster.

Ghép toàn bộ pipeline ELT của phase 3 thành MỘT đồ thị tài sản dữ liệu (asset graph):

    Postgres ──▶ [ingestion]  olist/* (9 bảng raw)         ← Python, có retry
                     │
                     ▼
                 [dbt]        stg_* → int_* → snapshot → dim_* / fact_*   ← mỗi model dbt = 1 asset
                     │
                     ▼
                 [reporting]  daily_kpi_report             ← Python đọc marts, ghi file báo cáo

Chạy giao diện web:   .venv/Scripts/dagster dev -f phase4_orchestration/definitions.py
                      rồi mở http://localhost:3000
Chạy không giao diện: .venv/Scripts/dagster job execute -f phase4_orchestration/definitions.py -j daily_refresh

Khái niệm chính:
  - ASSET    : một "thứ" dữ liệu tồn tại lâu dài (bảng, file). Dagster quản lý asset, không chỉ quản lý task.
  - DEPENDENCY: asset B khai báo cần asset A -> Dagster luôn chạy A trước B, A fail thì B không chạy.
  - JOB      : một tập asset được chạy cùng nhau.
  - SCHEDULE : chạy job theo lịch (cron).
  - RETRY    : tự thử lại khi lỗi tạm thời (mạng chập chờn, DB nguồn bận).
"""
import os
import sys
from datetime import datetime
from pathlib import Path

import duckdb
from dagster import (
    AssetExecutionContext,
    AssetKey,
    AssetSpec,
    Backoff,
    Definitions,
    MaterializeResult,
    MetadataValue,
    RetryPolicy,
    ScheduleDefinition,
    asset,
    define_asset_job,
    multi_asset,
)
from dagster_dbt import DagsterDbtTranslator, DbtCliResource, DbtProject, dbt_assets

ROOT = Path(__file__).resolve().parent.parent
DBT_PROJECT_DIR = ROOT / "phase3_dbt" / "shoplens"
WAREHOUSE_PATH = ROOT / "warehouse" / "shoplens_elt.duckdb"
REPORT_DIR = ROOT / "warehouse" / "reports"

# Tái sử dụng code EL của phase 3 (không viết lại)
sys.path.insert(0, str(ROOT / "phase3_dbt"))
import el_raw  # noqa: E402

# dbt trên Windows đọc file bằng cp1252; bật UTF-8 cho chắc ăn khi Dagster gọi dbt
os.environ.setdefault("PYTHONUTF8", "1")
# Cho Dagster tìm thấy lệnh `dbt` trong venv dù chưa activate venv
# (`dagster dev` gọi dbt parse qua PATH trong prepare_if_dev)
VENV_SCRIPTS = str(Path(sys.executable).parent)
os.environ["PATH"] = VENV_SCRIPTS + os.pathsep + os.environ.get("PATH", "")


# =====================================================================
# 1. INGESTION: 9 bảng raw = 9 asset, do MỘT hàm Python tạo ra (multi_asset).
#    Asset key ["olist", "<bảng>"] TRÙNG với tên source trong dbt (_sources.yml: source 'olist')
#    -> Dagster tự nối: raw table ──▶ model dbt dùng source đó.
# =====================================================================
@multi_asset(
    specs=[AssetSpec(key=AssetKey(["olist", t]), group_name="ingestion",
                     description=f"Bảng raw.{t}: copy nguyên trạng từ Postgres")
           for t in el_raw.TABLES],
    # Nguồn có thể chập chờn -> thử lại 3 lần, mỗi lần chờ lâu hơn (5s, 10s, 20s)
    retry_policy=RetryPolicy(max_retries=3, delay=5, backoff=Backoff.EXPONENTIAL),
)
def olist_raw_tables(context: AssetExecutionContext):
    counts = el_raw.extract_load(log=context.log.info)
    for table, n in counts.items():
        yield MaterializeResult(asset_key=AssetKey(["olist", table]),
                                metadata={"row_count": MetadataValue.int(n)})


# =====================================================================
# 2. TRANSFORMATION: toàn bộ dbt project. dagster-dbt đọc manifest của dbt và biến
#    MỖI model / snapshot / seed thành một asset, MỖI dbt test thành một "asset check".
# =====================================================================
dbt_project = DbtProject(project_dir=DBT_PROJECT_DIR)
dbt_project.prepare_if_dev()  # khi chạy `dagster dev`: tự `dbt parse` để có manifest mới nhất


class LayerGroupTranslator(DagsterDbtTranslator):
    """Nhóm asset dbt theo tầng (staging / intermediate / snapshots / marts / seeds) cho sơ đồ dễ nhìn."""

    def get_group_name(self, dbt_resource_props) -> str:
        return dbt_resource_props.get("config", {}).get("schema") or "dbt"


@dbt_assets(manifest=dbt_project.manifest_path, dagster_dbt_translator=LayerGroupTranslator())
def shoplens_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    # `dbt build` = seed + run + snapshot + test, đúng thứ tự DAG của dbt
    yield from dbt.cli(["build"], context=context).stream()


# =====================================================================
# 3. REPORTING: một asset Python đứng SAU dbt. Chỉ chạy khi marts đã dựng xong và test đạt.
# =====================================================================
@asset(
    deps=[AssetKey(["marts", "fact_orders"]), AssetKey(["marts", "dim_date"])],  # key = <schema>/<model>
    group_name="reporting",
    description="Báo cáo KPI theo tháng (file CSV) cho sếp, đọc từ marts",
)
def daily_kpi_report(context: AssetExecutionContext) -> MaterializeResult:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORT_DIR / "monthly_kpi.csv"
    with duckdb.connect(str(WAREHOUSE_PATH), read_only=True) as con:
        rel = con.sql("""
            SELECT d.year_month,
                   COUNT(*)                                AS orders,
                   ROUND(SUM(f.items_value), 2)            AS revenue_brl,
                   ROUND(AVG(f.review_score), 2)           AS avg_review,
                   ROUND(100.0 * AVG(f.is_late::INT), 1)   AS pct_late
            FROM marts.fact_orders f
            JOIN marts.dim_date d ON d.date_key = f.purchase_date_key
            WHERE f.order_status = 'delivered'
            GROUP BY 1 ORDER BY 1
        """)
        df = rel.df()
    df.to_csv(out, index=False)
    context.log.info(f"Đã ghi {len(df)} tháng vào {out}")

    # Bảng markdown nhỏ để xem trước ngay trên giao diện Dagster
    tail = df.tail(6).astype(str)
    preview = "\n".join(["| " + " | ".join(tail.columns) + " |",
                         "|" + "---|" * len(tail.columns)]
                        + ["| " + " | ".join(row) + " |" for row in tail.values])
    return MaterializeResult(metadata={
        "path": MetadataValue.path(str(out)),
        "months": MetadataValue.int(len(df)),
        "preview": MetadataValue.md(preview),
        "generated_at": MetadataValue.text(datetime.now().isoformat(timespec="seconds")),
    })


# =====================================================================
# 4. JOB + SCHEDULE: chạy TẤT CẢ asset mỗi ngày lúc 02:00 (giờ máy)
# =====================================================================
daily_refresh = define_asset_job("daily_refresh", selection="*",
                                 description="EL → dbt build → báo cáo")

daily_schedule = ScheduleDefinition(job=daily_refresh, cron_schedule="0 2 * * *",
                                    execution_timezone="Asia/Ho_Chi_Minh")

defs = Definitions(
    assets=[olist_raw_tables, shoplens_dbt_assets, daily_kpi_report],
    jobs=[daily_refresh],
    schedules=[daily_schedule],
    resources={"dbt": DbtCliResource(project_dir=dbt_project)},
)
