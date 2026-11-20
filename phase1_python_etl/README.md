# Phase 1: ETL bằng Python (Postgres → DuckDB)

## 1. Khái niệm (5 phút)

**ETL** = **E**xtract → **T**ransform → **L**oad: copy data từ nguồn sang warehouse, làm sạch dọc đường.

| Bước | Làm gì | Ở project này |
|---|---|---|
| **Extract** | Đọc từ nguồn, *không sửa nguồn*, lấy càng ít càng tốt | `SELECT` từ Postgres |
| **Transform** | Làm sạch, chuẩn hoá, áp quy tắc nghiệp vụ | pandas (Python), **bên ngoài** warehouse |
| **Load** | Ghi vào warehouse | `INSERT` vào DuckDB, schema `clean` |

**Vì sao DuckDB?** Nó là một *column-store* OLAP database, chỉ gồm 1 file, không cần server.
Về vai trò, nó giống Snowflake/BigQuery nhưng miễn phí và chạy local.

### 4 khái niệm quan trọng nhất của phase này

**① Full load và Incremental load**
- *Full*: mỗi lần chạy lấy **hết** bảng, thay toàn bộ. Đơn giản, dùng cho bảng nhỏ (customers, products).
- *Incremental*: chỉ lấy phần **mới** kể từ lần trước. Bắt buộc với bảng lớn (orders có thể lên tỷ dòng).

**② Watermark**: "vạch mốc" ghi lại *đã lấy dữ liệu tới đâu*. Lưu trong `etl_meta.watermarks`.
Lần chạy sau lấy `WHERE order_purchase_timestamp > watermark`. Giống cái bookmark khi đọc sách.

**③ Idempotency (luỹ đẳng)**: chạy **1 lần hay 10 lần đều cho cùng kết quả**. Đây là quy tắc vàng của data
engineering, vì pipeline *luôn* có lúc fail giữa chừng và phải chạy lại. Cách làm: `DELETE` các khoá sắp
nạp rồi mới `INSERT` (upsert), không bao giờ chỉ `INSERT` mù.

**④ Transaction**: toàn bộ lần chạy nằm trong 1 transaction. Lỗi giữa chừng thì `ROLLBACK`: warehouse
không bị "nửa nạc nửa mỡ", **watermark không bị dời** nên lần sau chạy lại đúng chỗ.

## 2. Luồng

```
                 ┌──────────────── pipeline.py (điều phối) ─────────────────┐
                 │                                                          │
Postgres ──E──▶ extract.py ──DataFrame thô──▶ transform.py ──DataFrame sạch──▶ load.py ──▶ DuckDB
(nguồn)          │  full: SELECT *                 │ bỏ dấu tên thành phố        │ BEGIN       warehouse/
                 │  incr: WHERE ts > watermark     │ dịch category, NULL→unknown │ DELETE+INSERT shoplens.duckdb
                 │                                 │ gộp 1 triệu geo → 19k zip   │ dời watermark  ├ clean.*
                 │                                 │ 1 review mới nhất / đơn     │ ghi run_log    └ etl_meta.*
                 │                                 │ gắn cờ chất lượng           │ COMMIT
```

| File | Vai trò |
|---|---|
| [config.py](config.py) | Địa chỉ nguồn/đích, bảng nào full, bảng nào incremental |
| [extract.py](extract.py) | **E**: SQL đọc nguồn, full và incremental theo watermark |
| [transform.py](transform.py) | **T**: mọi quy tắc làm sạch nằm ở một chỗ |
| [load.py](load.py) | **L**: DDL warehouse, `load_replace`, `load_upsert`, watermark, run log |
| [pipeline.py](pipeline.py) | Ghép E→T→L, quản lý transaction, CLI |
| [inspect_warehouse.py](inspect_warehouse.py) | Soi kết quả, so với nỗi đau phase 0 |

## 3. Chạy: mô phỏng pipeline chạy qua nhiều ngày

Olist là bản chụp tĩnh, nên `--as-of` giả lập "hôm nay là ngày X, pipeline chỉ thấy đơn trước X".

```bash
P=".venv/Scripts/python phase1_python_etl/pipeline.py"
rm -f warehouse/shoplens.duckdb
$P --as-of 2018-01-01        # lần chạy đầu
$P --as-of 2018-01-01        # chạy lại y hệt -> thử idempotency
$P --as-of 2018-06-01        # 5 tháng sau -> incremental
$P                           # tới hiện tại
$P --lookback-days 30        # cố tình xử lý lại 30 ngày cuối
.venv/Scripts/python phase1_python_etl/inspect_warehouse.py
```

## 4. Điều cần quan sát (kết quả thật)

| Lần chạy | as_of | Watermark trước → sau | Đơn extract | Tổng đơn trong warehouse | Bài học |
|---|---|---|---|---|---|
| 1 | 2018-01-01 | 1900 → 2017-12-31 | 45,430 | 45,430 | Lần đầu = lấy hết lịch sử |
| 2 | 2018-01-01 | giữ nguyên | **0** | 45,430 | Watermark chặn việc lấy lại |
| 3 | 2018-06-01 | → 2018-05-31 | 35,020 | 80,450 | Chỉ lấy phần mới |
| 4 | hiện tại | → 2018-10-17 | 18,991 | **99,441** ✅ khớp nguồn | |
| 5 | lookback 30 ngày | giữ nguyên | 8 (đã có sẵn) | **99,441** ✅ không nhân đôi | **Idempotency**: xử lý lại an toàn |

**Transform đã giải quyết được gì so với phase 0:**
- `sao paulo` / `são paulo` / `sa£o paulo` → **1 tên duy nhất**. Geolocation 1,000,163 dòng → 19,015 zip.
- Category: 0 NULL, 0 chưa dịch (610 sản phẩm gắn nhãn `unknown`, 2 bản dịch bổ sung bằng tay).
- Reviews: 551 review cũ bị gộp, giờ `order_id` là khoá duy nhất.
- Query "top category 2018": từ 4 JOIN + COALESCE còn **2 JOIN**, kết quả **khớp từng con số** với phase 0.
- 775 đơn không có món, 8 đơn thiếu ngày giao: **gắn cờ** (`has_items`, `is_delivered_missing_date`),
  **không xoá**. Xoá data là quyết định nghiệp vụ, không phải của engineer.

## 5. Điểm yếu của ETL kiểu này (lý do có phase 2, 3)

1. **Mất dữ liệu thô.** Warehouse chỉ chứa data *đã* transform. Nếu mai quy tắc đổi (ví dụ "giữ review *đầu tiên*
   chứ không phải mới nhất") thì phải Extract lại từ nguồn. Đó là lý do ngành chuyển sang **ELT** (phase 3):
   Load data thô trước, Transform sau, trong warehouse.
2. **Transform bằng pandas** chạy trong RAM của một máy. Với 1 tỷ dòng thì không nổi. Warehouse (Snowflake…)
   có sức mạnh tính toán khổng lồ, nên đẩy phần T vào đó.
3. **Watermark theo ngày mua bỏ sót cập nhật muộn.** Đơn mua ngày 30/12 lúc đó còn `shipped`, tuần sau mới
   thành `delivered`. Watermark đã qua 30/12 nên không bao giờ lấy lại đơn đó. Có 3 cách xử lý:
   `--lookback-days` (lấy lùi lại N ngày, an toàn nhờ idempotency), watermark theo cột `updated_at`
   (Olist không có cột này), hoặc **CDC** (Change Data Capture, đọc log thay đổi của DB, ví dụ Debezium).
4. **Vẫn còn** bẫy `customer_id`, fan-out, mất lịch sử. *Làm sạch* chưa đủ, cần **mô hình hoá**. Đó là phase 2.

## 6. Câu hỏi tự kiểm tra

1. Nếu `load_upsert` chỉ `INSERT` mà không `DELETE` trước, lần chạy 5 (lookback) sẽ gây ra chuyện gì?
   <details><summary>Đáp án</summary>8 đơn bị chèn lần thứ 2. Có PK thì pipeline lỗi; không có PK thì doanh thu bị đếm đôi một cách âm thầm, còn tệ hơn.</details>
2. Vì sao bước "dời watermark" phải nằm **trong** transaction cùng với việc nạp data?
   <details><summary>Đáp án</summary>Nếu watermark dời mà data chưa nạp xong (crash), lần sau pipeline bỏ qua đoạn đó và data mất vĩnh viễn. Ngược lại, data nạp xong mà watermark chưa dời thì lần sau nạp lại, nhưng nhờ idempotency nên vẫn an toàn.</details>
3. Vì sao `customers` dùng full load chứ không incremental? Khi nào phải đổi?
   <details><summary>Đáp án</summary>Bảng nhỏ (99k dòng) và không có cột thời gian để làm watermark. Khi lên hàng chục triệu dòng thì full load quá chậm, lúc đó cần nguồn thêm `updated_at` hoặc dùng CDC.</details>

---
⏭️ **Phase 2**: dựng **star schema** (fact + dimension) trên `clean.*` để diệt bẫy `customer_id` và fan-out.
