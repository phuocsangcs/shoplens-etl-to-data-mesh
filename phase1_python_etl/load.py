"""
L - LOAD: ghi dữ liệu đã sạch vào warehouse (DuckDB), schema `clean`.

Hai chiến lược, cả hai đều IDEMPOTENT (chạy lại bao nhiêu lần, kết quả vẫn như chạy 1 lần):
  - replace : xoá hết bảng rồi chèn lại           (bảng FULL LOAD)
  - upsert  : xoá các đơn sắp chèn, rồi chèn lại  (bảng INCREMENTAL, theo khoá order_id)

Mọi thứ trong một TRANSACTION: hoặc xong hết, hoặc không có gì thay đổi.
"""
import duckdb
import pandas as pd

# Schema đích được KHAI BÁO TRƯỚC (không để pandas tự đoán kiểu) -> kiểm soát được kiểu dữ liệu.
DDL = """
CREATE SCHEMA IF NOT EXISTS clean;
CREATE SCHEMA IF NOT EXISTS etl_meta;

CREATE TABLE IF NOT EXISTS clean.product_category_name_translation (
    product_category_name VARCHAR PRIMARY KEY, product_category_name_english VARCHAR);

CREATE TABLE IF NOT EXISTS clean.customers (
    customer_id VARCHAR PRIMARY KEY, customer_unique_id VARCHAR, customer_zip_code_prefix VARCHAR,
    customer_city VARCHAR, customer_state VARCHAR);

CREATE TABLE IF NOT EXISTS clean.sellers (
    seller_id VARCHAR PRIMARY KEY, seller_zip_code_prefix VARCHAR, seller_city VARCHAR, seller_state VARCHAR);

CREATE TABLE IF NOT EXISTS clean.products (
    product_id VARCHAR PRIMARY KEY, product_category_name VARCHAR,
    product_name_length INT, product_description_length INT, product_photos_qty INT,
    product_weight_g INT, product_length_cm INT, product_height_cm INT, product_width_cm INT,
    product_category_name_english VARCHAR);

CREATE TABLE IF NOT EXISTS clean.geolocation (
    zip_code_prefix VARCHAR PRIMARY KEY, lat DOUBLE, lng DOUBLE, city VARCHAR, state VARCHAR);

CREATE TABLE IF NOT EXISTS clean.orders (
    order_id VARCHAR PRIMARY KEY, customer_id VARCHAR, order_status VARCHAR,
    order_purchase_timestamp TIMESTAMP, order_approved_at TIMESTAMP,
    order_delivered_carrier_date TIMESTAMP, order_delivered_customer_date TIMESTAMP,
    order_estimated_delivery_date TIMESTAMP,
    has_items BOOLEAN, is_delivered_missing_date BOOLEAN);

CREATE TABLE IF NOT EXISTS clean.order_items (
    order_id VARCHAR, order_item_id INT, product_id VARCHAR, seller_id VARCHAR,
    shipping_limit_date TIMESTAMP, price DOUBLE, freight_value DOUBLE,
    PRIMARY KEY (order_id, order_item_id));

CREATE TABLE IF NOT EXISTS clean.order_payments (
    order_id VARCHAR, payment_sequential INT, payment_type VARCHAR,
    payment_installments INT, payment_value DOUBLE,
    PRIMARY KEY (order_id, payment_sequential));

CREATE TABLE IF NOT EXISTS clean.order_reviews (
    review_id VARCHAR, order_id VARCHAR PRIMARY KEY, review_score INT,
    review_comment_title VARCHAR, review_comment_message VARCHAR,
    review_creation_date TIMESTAMP, review_answer_timestamp TIMESTAMP);

-- Watermark: "đã lấy dữ liệu tới thời điểm nào" -> lần chạy sau tiếp tục từ đây
CREATE TABLE IF NOT EXISTS etl_meta.watermarks (
    name VARCHAR PRIMARY KEY, value TIMESTAMP, updated_at TIMESTAMP);

-- Nhật ký mỗi lần chạy: phục vụ debug & giám sát
CREATE TABLE IF NOT EXISTS etl_meta.run_log (
    run_id VARCHAR, table_name VARCHAR, mode VARCHAR, as_of TIMESTAMP,
    rows_extracted INT, rows_loaded INT, dropped VARCHAR, finished_at TIMESTAMP);
"""

WATERMARK_NAME = "orders.order_purchase_timestamp"


def connect(path) -> duckdb.DuckDBPyConnection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    con.execute(DDL)
    return con


def get_watermark(con) -> pd.Timestamp | None:
    row = con.execute("SELECT value FROM etl_meta.watermarks WHERE name = ?", [WATERMARK_NAME]).fetchone()
    return row[0] if row else None


def set_watermark(con, value) -> None:
    con.execute("""INSERT OR REPLACE INTO etl_meta.watermarks VALUES (?, ?, now())""", [WATERMARK_NAME, value])


def _insert(con, table: str, df: pd.DataFrame) -> None:
    con.register("df_batch", df)  # DuckDB đọc thẳng DataFrame trong RAM, không cần ghi file trung gian
    cols = ", ".join(df.columns)
    con.execute(f"INSERT INTO clean.{table} ({cols}) SELECT {cols} FROM df_batch")
    con.unregister("df_batch")


def load_replace(con, table: str, df: pd.DataFrame) -> int:
    """FULL: DELETE all + INSERT. Chạy lại -> vẫn đúng một bản."""
    con.execute(f"DELETE FROM clean.{table}")
    _insert(con, table, df)
    return len(df)


def load_upsert(con, table: str, df: pd.DataFrame, key: str = "order_id") -> int:
    """
    INCREMENTAL: xoá các dòng có cùng khoá với batch mới, rồi chèn batch.
    Nếu batch này đã được nạp trước đó (chạy lại / chạy chồng lấn) -> dòng cũ bị thay, KHÔNG bị nhân đôi.
    """
    if df.empty:
        return 0
    con.register("keys_batch", df[[key]].drop_duplicates())
    con.execute(f"DELETE FROM clean.{table} WHERE {key} IN (SELECT {key} FROM keys_batch)")
    con.unregister("keys_batch")
    _insert(con, table, df)
    return len(df)


def log_run(con, run_id, table, mode, as_of, n_extracted, n_loaded, dropped: dict) -> None:
    dropped_txt = "; ".join(f"{k}: {v}" for k, v in dropped.items() if v) or None
    con.execute("INSERT INTO etl_meta.run_log VALUES (?, ?, ?, ?, ?, ?, ?, now())",
                [run_id, table, mode, as_of, n_extracted, n_loaded, dropped_txt])
