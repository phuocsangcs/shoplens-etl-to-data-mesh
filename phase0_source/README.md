# Phase 0: Nguồn dữ liệu (OLTP) và vì sao không phân tích thẳng trên đó

## 1. Khái niệm (5 phút)

Mọi pipeline dữ liệu bắt đầu từ **nguồn** (source). Nguồn phổ biến nhất là **DB của app**,
cái mà bạn vẫn code backend hằng ngày. Dân data gọi nó là **OLTP** (Online Transaction Processing).

| | OLTP (DB của app) | OLAP (Data Warehouse) |
|---|---|---|
| Phục vụ ai | Người dùng app | Analyst, sếp, dashboard, ML |
| Kiểu thao tác | INSERT/UPDATE từng dòng, rất nhiều lần/giây | SELECT quét hàng triệu dòng, GROUP BY |
| Thiết kế | Chuẩn hoá 3NF (nhiều bảng nhỏ) | Phi chuẩn hoá có chủ đích (star schema, phase 2) |
| Lưu trữ | Theo **dòng** (row-store) | Theo **cột** (column-store) |
| Lịch sử | Chỉ có trạng thái **hiện tại** (UPDATE đè) | Giữ **lịch sử** |
| Ví dụ | Postgres, MySQL | Snowflake, BigQuery, DuckDB |

## 2. Dataset: Olist (data thật)

[Brazilian E-Commerce by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce):
khoảng 100k đơn hàng thật trên một sàn TMĐT Brazil, 09/2016 → 10/2018, tiền tệ là BRL (real).
Olist là **marketplace**: nhiều **seller** bán hàng, sàn lo thanh toán và vận chuyển.

```
customers 1──n orders 1──n order_items n──1 products ── category_translation
                 │                    └──n──1 sellers
                 ├──n order_payments   (1 đơn có thể trả nhiều lần / nhiều cách)
                 └──n order_reviews    (khách chấm 1-5 sao)
geolocation: zip code → toạ độ (1 triệu dòng)
```

## 3. Luồng của phase này

```
data/raw/olist/*.csv ──load_olist.py (COPY)──▶ Postgres "shop" (port 5440)  ← giả lập DB production
                                                     │
                     analytics_pain.sql ─────────────┘  → thấy 6 nỗi đau
```

> `load_olist.py` **không phải ETL**. Nó chỉ dựng lại "thế giới thật" (một app DB đang chạy),
> để từ phase 1 ta có chỗ để **Extract**.

| File | Vai trò |
|---|---|
| [schema.sql](schema.sql) | Schema OLTP: khoá chính, khoá ngoại. Giữ nguyên tên cột gốc, kể cả lỗi chính tả `lenght` |
| [load_olist.py](load_olist.py) | Stream 9 file CSV vào Postgres bằng `COPY` (khoảng 1.5 triệu dòng, ~15 giây) |
| [analytics_pain.sql](analytics_pain.sql) | 6 query "làm analyst trên DB production" |

## 4. Chạy

```bash
docker compose up -d                                   # bật Postgres
.venv/Scripts/python phase0_source/load_olist.py       # nạp CSV (chạy lại được nhiều lần)
docker exec -i shoplens-source-db psql -U shop -d shop < phase0_source/analytics_pain.sql
```

Muốn tự xem data: `docker exec -it shoplens-source-db psql -U shop -d shop` rồi gõ SQL.

## 5. Điều cần quan sát (kết quả thật)

| # | Nỗi đau | Con số thật | Phase giải quyết |
|---|---------|-------------|------------------|
| 1 | **Data bẩn** | "São Paulo" có 4 cách viết (`sao paulo`, `são paulo`, `sãopaulo`, `sa£o paulo`, cái cuối là lỗi encoding). 610 sản phẩm không có category, 2 category không có bản dịch, **814 `review_id` bị trùng** (tưởng là khoá chính), 775 đơn không có món nào, 8 đơn "delivered" nhưng không có ngày giao | Phase 1: Transform làm sạch **một lần**, mọi người dùng chung |
| 2 | **Bẫy nghiệp vụ ẩn** | Tỉ lệ khách quay lại tính theo `customer_id` = **0%**, theo `customer_unique_id` = **3.12%**. Olist sinh `customer_id` mới cho mỗi đơn | Phase 2: `dim_customer` mã hoá hiểu biết này **một lần** |
| 3 | **Fan-out khi JOIN** | Doanh thu đúng **13.22 triệu BRL**, nhưng JOIN thêm payments thì ra **13.81 triệu** (dư khoảng 592k BRL) | Phase 2: khái niệm **grain** của bảng fact |
| 4 | **Query phức tạp** | "Top category 2018" cần 4 JOIN, `LEFT JOIN` bảng dịch và `COALESCE` cho NULL | Phase 2: star schema, query còn 1–2 JOIN |
| 5 | **Data cụt hai đầu** | 2018-08 có 6,512 đơn, sang 2018-09 chỉ còn **16 đơn**. Không phải sàn sập mà bản export bị cắt. Vẽ biểu đồ ngây thơ sẽ kết luận sai. (Cũng thấy đỉnh Black Friday 2017-11: 7,544 đơn) | Phase 5: kiểm tra freshness/completeness |
| 6 | **Tranh tài nguyên** | `EXPLAIN` cho thấy *Seq Scan* toàn bảng. Row-store phải đọc cả dòng chỉ để SUM cột `price` | Phase 1: copy data **sang chỗ khác** (warehouse, column-store) |

> 💡 **Ý chính:** SQL không khó. Cái khó là *mỗi analyst tự làm sạch và tự hiểu nghiệp vụ theo cách
> riêng → mỗi báo cáo một con số*, và *query phân tích làm hại app*. ETL + Data Warehouse sinh ra để
> giải đúng hai việc đó: **một nơi riêng, một phiên bản sự thật đã làm sạch** (single source of truth).

## 6. Câu hỏi tự kiểm tra

1. Vì sao không thêm index vào Postgres để giải nỗi đau #6?
   <details><summary>Gợi ý</summary>Index giúp tìm vài dòng, không giúp khi phải SUM cả bảng. Index còn làm chậm INSERT của app. Vấn đề gốc là OLTP và OLAP có nhu cầu trái ngược nhau.</details>
2. Sếp hỏi "doanh thu theo phương thức thanh toán (credit_card, boleto…)". Nên SUM cột nào, ở bảng nào, và có JOIN `order_items` không?
   <details><summary>Gợi ý</summary>SUM `order_payments.payment_value` và không JOIN order_items. Câu hỏi ở grain "mỗi lần thanh toán", JOIN với items sẽ gây fan-out theo chiều ngược lại.</details>
3. Ai trong công ty biết "`customer_id` không phải là người thật"? Nếu team data trung tâm phải tự khám phá
   hàng trăm cái bẫy như vậy cho mọi bộ phận (bán hàng, vận chuyển, seller, marketing…), chuyện gì xảy ra?
   <details><summary>Gợi ý</summary>Team trung tâm thành nút cổ chai và hiểu sai nghiệp vụ. Người hiểu data nhất là team sở hữu nguồn. Đây chính là lập luận mở đầu của Data Mesh (phase 6): giao trách nhiệm data cho domain.</details>

---
⏭️ **Phase 1**: viết ETL bằng Python: Extract từ Postgres → Transform (làm sạch nỗi đau #1) → Load vào DuckDB.
