"""Cấu hình dùng chung cho pipeline Phase 1."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# NGUỒN: Postgres (DB của app) - chỉ ĐỌC, không bao giờ ghi vào
SOURCE_DB_URL = os.getenv("SOURCE_DB_URL", "postgresql://shop:shop@localhost:5440/shop")

# ĐÍCH: DuckDB - một file duy nhất, đóng vai Data Warehouse (giống Snowflake nhưng chạy local)
WAREHOUSE_PATH = Path(os.getenv("WAREHOUSE_PATH", ROOT / "warehouse" / "shoplens.duckdb"))

# Bảng "nhỏ, ít đổi" -> FULL LOAD: mỗi lần chạy lấy hết, thay toàn bộ
FULL_LOAD_TABLES = ["product_category_name_translation", "customers", "sellers", "products", "geolocation"]

# Bảng "lớn, tăng liên tục" -> INCREMENTAL LOAD: chỉ lấy đơn MỚI kể từ lần chạy trước
INCREMENTAL_TABLES = ["orders", "order_items", "order_payments", "order_reviews"]
