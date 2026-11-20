"""
Phase 1: Pipeline ETL hoàn chỉnh:  Postgres --E--> Python --T--> --L--> DuckDB

Chạy:
  # Giả lập: hôm nay là 2018-01-01, chạy pipeline lần đầu
  .venv/Scripts/python phase1_python_etl/pipeline.py --as-of 2018-01-01

  # Giả lập: hôm nay là 2018-06-01 -> chỉ lấy đơn MỚI từ lần trước (incremental)
  .venv/Scripts/python phase1_python_etl/pipeline.py --as-of 2018-06-01

  # Chạy với dữ liệu tới hiện tại
  .venv/Scripts/python phase1_python_etl/pipeline.py

  # Xoá watermark, nạp lại toàn bộ từ đầu
  .venv/Scripts/python phase1_python_etl/pipeline.py --full-refresh

Vì dataset Olist là bản chụp tĩnh, `--as-of` giả lập "pipeline đang chạy vào ngày X":
chỉ thấy các đơn mua trước ngày X.
"""
import argparse
import time
import uuid
from datetime import datetime, timedelta

import psycopg

import config
import extract as E
import transform as T
import load as L

EPOCH = datetime(1900, 1, 1)


def run(as_of: datetime, full_refresh: bool, lookback_days: int) -> None:
    run_id = uuid.uuid4().hex[:8]
    t0 = time.perf_counter()
    print(f"▶ run {run_id} | as_of = {as_of:%Y-%m-%d %H:%M}")

    with psycopg.connect(config.SOURCE_DB_URL) as src, L.connect(config.WAREHOUSE_PATH) as wh:
        # ---------- 1. Xác định cửa sổ incremental ----------
        if full_refresh:
            wh.execute("DELETE FROM etl_meta.watermarks")
        watermark = L.get_watermark(wh) or EPOCH
        start = watermark - timedelta(days=lookback_days) if watermark > EPOCH else EPOCH
        print(f"  watermark hiện tại = {watermark:%Y-%m-%d %H:%M}"
              + (f"  (lookback {lookback_days} ngày -> lấy từ {start:%Y-%m-%d})" if lookback_days and watermark > EPOCH else ""))

        wh.execute("BEGIN TRANSACTION")  # mọi thay đổi bên dưới: thành công hết hoặc huỷ hết
        try:
            # ---------- 2. Bảng FULL LOAD ----------
            raw = {t: E.extract_full(src, t) for t in config.FULL_LOAD_TABLES}

            translation, d = T.transform_product_category_name_translation(raw["product_category_name_translation"])
            results = {
                "product_category_name_translation": (translation, d),
                "customers":   T.transform_customers(raw["customers"]),
                "sellers":     T.transform_sellers(raw["sellers"]),
                "products":    T.transform_products(raw["products"], translation),
                "geolocation": T.transform_geolocation(raw["geolocation"]),
            }
            for table, (df, dropped) in results.items():
                n = L.load_replace(wh, table, df)
                L.log_run(wh, run_id, table, "full", as_of, len(raw[table]), n, dropped)
                print(f"  [full]  {table:<34} extract {len(raw[table]):>9,} → load {n:>8,}  {_fmt(dropped)}")

            # ---------- 3. Bảng INCREMENTAL ----------
            raw = {t: E.extract_incremental(src, t, start, as_of) for t in config.INCREMENTAL_TABLES}

            results = {
                "orders":         T.transform_orders(raw["orders"], raw["order_items"]),
                "order_items":    T.transform_order_items(raw["order_items"]),
                "order_payments": T.transform_order_payments(raw["order_payments"]),
                "order_reviews":  T.transform_order_reviews(raw["order_reviews"]),
            }
            for table, (df, dropped) in results.items():
                n = L.load_upsert(wh, table, df)
                L.log_run(wh, run_id, table, "incremental", as_of, len(raw[table]), n, dropped)
                print(f"  [incr]  {table:<34} extract {len(raw[table]):>9,} → load {n:>8,}  {_fmt(dropped)}")

            # ---------- 4. Dời watermark tới đơn mới nhất vừa nạp ----------
            orders = raw["orders"]
            if not orders.empty:
                new_wm = max(orders["order_purchase_timestamp"].max().to_pydatetime(), watermark)
                L.set_watermark(wh, new_wm)
                print(f"  watermark mới       = {new_wm:%Y-%m-%d %H:%M}")
            else:
                print("  không có đơn mới, watermark giữ nguyên")

            wh.execute("COMMIT")
        except Exception:
            wh.execute("ROLLBACK")  # lỗi giữa chừng -> warehouse không bị "nửa nạc nửa mỡ", watermark không bị dời
            raise

        total = wh.execute("SELECT COUNT(*) FROM clean.orders").fetchone()[0]
    print(f"✔ xong sau {time.perf_counter() - t0:.1f}s | tổng số đơn trong warehouse: {total:,}")


def _fmt(dropped: dict) -> str:
    items = [f"{k}: {v:,}" for k, v in dropped.items() if v]
    return f"(loại/gộp: {'; '.join(items)})" if items else ""


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="ShopLens Phase 1 ETL")
    p.add_argument("--as-of", type=datetime.fromisoformat, default=datetime.now(),
                   help="giả lập thời điểm chạy pipeline (YYYY-MM-DD)")
    p.add_argument("--full-refresh", action="store_true", help="bỏ watermark, nạp lại từ đầu")
    p.add_argument("--lookback-days", type=int, default=0,
                   help="lấy lùi lại N ngày trước watermark để bắt dữ liệu cập nhật muộn")
    args = p.parse_args()
    run(args.as_of, args.full_refresh, args.lookback_days)
