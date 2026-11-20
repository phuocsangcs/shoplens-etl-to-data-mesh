"""
Giả lập: 500 khách đang ở São Paulo (SP) CHUYỂN NHÀ tới Rio de Janeiro (RJ).
App production làm đúng kiểu OLTP: UPDATE ĐÈ địa chỉ trong Postgres, không giữ lịch sử.

Chạy:  .venv/Scripts/python phase3_dbt/simulate_address_changes.py
Hoàn tác: chạy lại phase0_source/load_olist.py (nạp lại nguồn gốc).

Olist là bản chụp tĩnh nên không có ai đổi địa chỉ "trong lúc pipeline đang chạy".
Script này tạo ra tình huống đó để xem snapshot (SCD2) bắt được thay đổi.
"""
import os

import psycopg

SOURCE_DB_URL = os.getenv("SOURCE_DB_URL", "postgresql://shop:shop@localhost:5440/shop")

SQL = """
WITH latest AS (          -- dòng customer của ĐƠN GẦN NHẤT mỗi người = "địa chỉ hiện tại"
    SELECT DISTINCT ON (c.customer_unique_id) c.customer_id, c.customer_unique_id, c.customer_state
    FROM customers c JOIN orders o USING (customer_id)
    -- tie-break theo customer_id GIỐNG HỆT int_customer_latest_address.sql,
    -- nếu không 2 bên có thể chọn 2 dòng khác nhau khi 1 người có 2 đơn cùng giây
    ORDER BY c.customer_unique_id, o.order_purchase_timestamp DESC, c.customer_id
),
movers AS (               -- chọn 500 người ở SP (cố định, chạy lại vẫn ra cùng nhóm)
    SELECT customer_id FROM latest
    WHERE customer_state = 'SP'
    ORDER BY md5(customer_unique_id)
    LIMIT 500
)
UPDATE customers
SET customer_city = 'rio de janeiro', customer_state = 'RJ', customer_zip_code_prefix = '20040'
WHERE customer_id IN (SELECT customer_id FROM movers)
RETURNING customer_unique_id
"""

with psycopg.connect(SOURCE_DB_URL) as conn, conn.cursor() as cur:
    cur.execute(SQL)
    moved = cur.fetchall()

print(f"Đã UPDATE địa chỉ của {len(moved)} khách: SP → RJ (ghi đè trong Postgres, lịch sử mất ở nguồn).")
if moved:
    print(f"Ví dụ một người: {moved[0][0]}")
print("Tiếp theo: chạy lại el_raw.py rồi `dbt build` để snapshot ghi nhận thay đổi.")
