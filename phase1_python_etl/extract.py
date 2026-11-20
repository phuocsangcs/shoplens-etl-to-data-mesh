"""
E - EXTRACT: đọc dữ liệu từ nguồn (Postgres), KHÔNG sửa gì cả.

Nguyên tắc:
  - Chỉ SELECT, không ghi vào nguồn.
  - Lấy càng ít càng tốt (chỉ phần mới) để không làm nặng DB của app.
"""
from datetime import datetime

import pandas as pd
import psycopg


def query_df(conn: psycopg.Connection, sql: str, params: dict | None = None) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d.name for d in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


def extract_full(conn: psycopg.Connection, table: str) -> pd.DataFrame:
    """FULL: lấy toàn bộ bảng. Dùng cho bảng nhỏ (customers, products...)."""
    return query_df(conn, f"SELECT * FROM {table}")


# Điều kiện chọn "đơn mới": mua SAU watermark (lần chạy trước) và TRƯỚC thời điểm chạy (as_of).
# Watermark = "vạch mốc" đánh dấu mình đã lấy tới đâu.
_NEW_ORDERS = """
    SELECT order_id FROM orders
    WHERE order_purchase_timestamp >  %(watermark)s
      AND order_purchase_timestamp <= %(as_of)s
"""

INCREMENTAL_SQL = {
    "orders":         f"SELECT * FROM orders         WHERE order_id IN ({_NEW_ORDERS})",
    "order_items":    f"SELECT * FROM order_items    WHERE order_id IN ({_NEW_ORDERS})",
    "order_payments": f"SELECT * FROM order_payments WHERE order_id IN ({_NEW_ORDERS})",
    "order_reviews":  f"SELECT * FROM order_reviews  WHERE order_id IN ({_NEW_ORDERS})",
}


def extract_incremental(conn: psycopg.Connection, table: str,
                        watermark: datetime, as_of: datetime) -> pd.DataFrame:
    """INCREMENTAL: chỉ lấy dòng thuộc các đơn mua trong khoảng (watermark, as_of]."""
    return query_df(conn, INCREMENTAL_SQL[table], {"watermark": watermark, "as_of": as_of})
