# ShopLens: Học ETL → Data Warehouse → Data Mesh qua một project

Dùng **data thật** của sàn TMĐT Brazil [Olist (Kaggle)](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
(khoảng 100k đơn, 2016–2018) để trả lời các câu hỏi business như *"doanh thu theo tháng / danh mục / bang?"*,
*"giao hàng có đúng hạn không?"*, *"seller nào bị đánh giá thấp?"*.
Project đi từ "query thẳng vào DB production" cho tới "mỗi domain tự sở hữu
data product" (Data Mesh), **mỗi phase giải quyết nỗi đau của phase trước**.

## Bức tranh tổng thể

```
 Phase 0           Phase 1-2                  Phase 3-5                 Phase 6
┌──────────┐     ┌─────────────┐   ┌──────────────────────────┐   ┌──────────────────┐
│ Postgres │ E   │ Python ETL  │   │ EL thô → dbt transform   │   │ Domain Sales     │
│ (OLTP,   │───▶ │ → DuckDB    │──▶│ raw → staging → marts    │──▶│  └ data product  │
│ app DB)  │     │ star schema │   │ + Dagster lập lịch       │   │ Domain Logistics │
└──────────┘     └─────────────┘   │ + test chất lượng        │   │  └ đọc qua       │
                                   └──────────────────────────┘   │    contract      │
   nguồn          ETL tự viết          ELT "chuẩn ngành"          └──────────────────┘
                                                                     phi tập trung
```

## Danh sách phase (đã chốt)

| # | Phase | Câu hỏi trả lời | Tool | Trạng thái |
|---|-------|-----------------|------|-----------|
| 0 | [Nguồn dữ liệu OLTP](phase0_source/README.md) | Data gốc trông thế nào? Vì sao không phân tích thẳng trên đó? | Postgres (Docker) | ✅ |
| 1 | [ETL bằng Python](phase1_python_etl/README.md) | Extract, Transform, Load thực chất là gì? Idempotent, incremental là gì? | Python, pandas, DuckDB | ✅ |
| 2 | [Star schema (Dimensional Modeling)](phase2_star_schema/README.md) | Thiết kế warehouse thế nào để query phân tích dễ & nhanh? Fact, dimension, grain? | SQL trên DuckDB | ✅ |
| 3 | [ELT với dbt](phase3_dbt/README.md) | Vì sao ngành chuyển từ ETL sang ELT? Phân tầng raw/staging/marts, test, lineage, SCD2 | dbt + DuckDB | ✅ |
| 4 | [Orchestration](phase4_orchestration/README.md) | Ai chạy pipeline mỗi đêm? Phụ thuộc, retry, lịch chạy | Dagster | ✅ |
| 5 | Data quality & phục vụ *(tuỳ chọn, tạm bỏ qua)* | Làm sao để người dùng *tin* data? Freshness, business rule test, báo cáo | dbt tests, Python | ⏭️ |
| 6 | [Data Mesh](phase6_data_mesh/README.md) | Chia warehouse tập trung thành các domain sở hữu data product có contract | 2 dbt project, data contract YAML, platform | ✅ |

Mỗi folder phase có `README.md` gồm: **khái niệm → luồng chạy → lệnh chạy → điều cần quan sát → câu hỏi tự kiểm tra**.

## Tổng kết

**Một câu:** phase 1–4 dạy **cách làm** data phân tích (kỹ thuật). Data Mesh dạy **ai làm và chia ranh giới
thế nào** (tổ chức). Bên trong mỗi domain vẫn là toàn bộ kỹ thuật của phase 1–4.

| Phase | Vấn đề | Lời giải | Ý cần nhớ |
|---|---|---|---|
| 0 | Phân tích thẳng trên DB của app: chậm, bẩn, dễ hiểu sai | Tách chỗ phân tích riêng | OLTP ≠ OLAP |
| 1 | Cần copy và làm sạch data | ETL bằng Python | Incremental, idempotent |
| 2 | Bảng sạch nhưng query vẫn khó | Star schema | Fact + dimension, grain |
| 3 | Code ETL tự viết khó bảo trì, khó test | ELT với dbt | Test, lineage, SCD2 |
| 4 | Ai chạy mỗi đêm, lỗi thì sao? | Dagster | Phụ thuộc, retry, lịch |
| 6 | Một team data thành nút cổ chai | Data Mesh | Domain sở hữu, giao tiếp qua contract |

**Data Mesh là gì, nói cho đúng:**
- Là **paradigm** (4 nguyên tắc), không phải tool. Cùng loại với microservices hay DDD.
- Dành cho **analytical data**. Phía operational đã có microservices: mỗi service một DB, giao tiếp qua API.
  Data Mesh chính là **mang tư tưởng microservices sang phía phân tích**.
- Trong một domain, team sở hữu **cả hai**: service (Postgres) ──EL/CDC──▶ data product (warehouse).
- **Không thay thế** warehouse, ELT hay star schema. Chỉ thêm **ranh giới sở hữu và contract** lên trên.

## Giải nghĩa nhanh vài thuật ngữ

- **OLTP (Online Transaction Processing)**: DB của app, ghi/đọc từng dòng (Postgres, MySQL). **OLAP (Online Analytical Processing)**: DB phân tích, quét hàng triệu dòng.
- **Data Warehouse**: DB OLAP gom data từ nhiều nguồn, đã làm sạch và mô hình hoá cho phân tích.
- **ETL / ELT**: Extract-Transform-Load. ELT đổ data thô vào warehouse trước rồi transform bằng SQL trong đó.
- **Snowflake** (sản phẩm): cloud data warehouse thương mại, giống BigQuery/Redshift. Project này dùng
  **DuckDB** (miễn phí, chạy local, SQL rất giống) thay thế. **Snowflake schema** là một kiểu mô hình
  hoá bảng, không liên quan tới sản phẩm trên.
- **Data Mesh**: cách *tổ chức*: mỗi domain business tự sở hữu pipeline + data product của mình.

## Chuẩn bị

```bash
# 1. Tải dataset Olist từ Kaggle, giải nén 9 file CSV vào data/raw/olist/
docker compose up -d                       # Postgres nguồn ở localhost:5440
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
```
