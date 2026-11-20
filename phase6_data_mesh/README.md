# Phase 6: Data Mesh

## 1. Nói đơn giản trước

Phase 1–4 xây **một warehouse trung tâm**, do **một team data** làm hết cho mọi bộ phận. Hồi ở phase 0
ta đã thấy vấn đề: cái bẫy `customer_id` chỉ người hiểu nghiệp vụ bán hàng mới biết. Công ty có 30 bộ phận
thì team data trung tâm thành **nút cổ chai** và **hiểu sai nghiệp vụ**.

**Data Mesh** (Zhamak Dehghani, 2019) đề xuất: **giao data về cho chính bộ phận hiểu nó nhất**. Mỗi bộ phận
(gọi là **domain**) tự làm pipeline của mình và **xuất bản** kết quả thành một **data product** có "giao kèo"
rõ ràng, để bộ phận khác dùng.

Với dân SE, phép so sánh dễ nhất là **monolith → microservices**:

| Software Engineering | Data Mesh | Trong project |
|---|---|---|
| Monolith | Warehouse trung tâm | Phase 1–4 |
| Microservice | **Domain** | `domains/sales`, `domains/logistics` |
| DB riêng của service | Warehouse riêng của domain | `sales.duckdb`, `logistics.duckdb` |
| **Public API** | **Output port** (data product) | `output.orders_v1` |
| Private code bên trong | Bảng nội bộ (raw, staging) | `staging.stg_sales__*` |
| **OpenAPI spec** | **Data contract** | `data_product.yml` |
| API versioning `/v1`, `/v2` | Version data product | `orders_v1` → `orders_v2` |
| Platform team (K8s, CI/CD) | **Self-serve data platform** | `platform/` |
| Linter / CI rule chung | **Federated governance** | `platform/validate_contracts.py` |
| Service registry | **Data catalog** | `platform/catalog.py` |

> ⚠️ Data Mesh là cách **tổ chức con người và trách nhiệm**, không phải một tool. Tool (dbt, DuckDB,
> Dagster) giữ nguyên như phase 3–4; chỉ có **ai sở hữu cái gì** và **giao tiếp qua đâu** là thay đổi.

## 2. Bốn nguyên tắc và chỗ thể hiện trong code

| # | Nguyên tắc | Ý nghĩa | Ở đâu |
|---|---|---|---|
| 1 | **Domain ownership** | Domain tự sở hữu data của mình, từ ingest đến xuất bản | Mỗi domain có `ingest.yml` (chỉ lấy cột mình sở hữu), dbt project riêng, warehouse riêng |
| 2 | **Data as a product** | Data xuất bản phải "dùng được như một sản phẩm": có owner, mô tả, schema cố định, SLA, version | `data_product.yml` + dbt **model contract** (`contract: enforced: true`) |
| 3 | **Self-serve platform** | Platform team làm công cụ chung, để domain không phải tự xây hạ tầng | `platform/ingest.py`, package dbt `dbt_platform` (macro `published_at`, `normalize_city`) |
| 4 | **Federated computational governance** | Luật chung do các domain thống nhất, kiểm tra **tự động bằng code** | `platform/policies.yml` + `validate_contracts.py` |

## 3. Kiến trúc

```
                         Postgres (hệ thống vận hành)
                       ┌────────────┴─────────────┐
           ingest.yml: │ chỉ cột bán hàng          │ chỉ cột giao hàng
                       ▼                           ▼
 ┌──────────── DOMAIN SALES ────────────┐   ┌────────── DOMAIN LOGISTICS ──────────┐
 │ owner: Sales Analytics               │   │ owner: Logistics & Fulfillment       │
 │ warehouse/mesh/sales.duckdb          │   │ warehouse/mesh/logistics.duckdb      │
 │                                      │   │                                      │
 │  raw.*  →  staging.* (nội bộ)        │   │  raw.*  →  staging.* (nội bộ)        │
 │                 │                    │   │                 │                    │
 │                 ▼                    │   │                 ▼                    │
 │  ╔═ output.orders_v1 ═══════════╗    │   │  ╔═ output.delivery_performance_v1 ═╗│
 │  ║ DATA PRODUCT  sales.orders   ║────┼──▶│  ║ DATA PRODUCT                     ║│
 │  ║ contract · SLA 24h · v1      ║ đọc│   │  ║ logistics.delivery_performance   ║│
 │  ╚══════════════════════════════╝ qua│   │  ╚══════════════════════════════════╝│
 └──────────────────│─────────────── port┘   └──────────────────│───────────────────┘
                    │      (read-only, chỉ schema output)       │
                    └──────────────────┬────────────────────────┘
                                       ▼
                         CONSUMER: consumers/exec_report.py
                         (JOIN 2 data product, không cần warehouse trung tâm)

 ┌────────────────────────────── PLATFORM (dùng chung) ──────────────────────────────┐
 │ ingest.py · dbt_platform (macros) · policies.yml · validate_contracts.py · catalog │
 └─────────────────────────────────────────────────────────────────────────────────────┘
```

**Logistics cần biết khách ở bang nào và chấm mấy sao**, nhưng đó là data của Sales. Logistics **không**
tự ingest bảng customers hay reviews, mà dùng data product `sales.orders` của Sales, chỉ qua output port.

> Olist là một DB nguyên khối nên cả hai domain cùng ingest từ một Postgres, mỗi bên chỉ lấy cột mình sở hữu.
> Ở công ty thật, mỗi domain có hệ thống vận hành riêng (app bán hàng, hệ thống vận chuyển).

### Cấu trúc thư mục

```
phase6_data_mesh/
├── platform/                         ← PLATFORM TEAM
│   ├── policies.yml                  luật chung (governance)
│   ├── ingest.py                     công cụ ingest self-serve
│   ├── dbt_platform/                 dbt package macro dùng chung
│   ├── validate_contracts.py         kiểm tra tự động mọi data product
│   ├── catalog.py                    danh bạ data product
│   └── mesh_lib.py
├── domains/
│   ├── sales/                        ← SALES TEAM
│   │   ├── ingest.yml                tôi cần bảng/cột nào
│   │   ├── data_product.yml          ⭐ data contract
│   │   └── dbt/                      models/staging (nội bộ) + models/output (công khai)
│   └── logistics/                    ← LOGISTICS TEAM
│       ├── ingest.yml
│       ├── data_product.yml
│       └── dbt/                      profiles.yml attach sales.duckdb READ-ONLY
├── consumers/exec_report.py          ← người dùng cuối
└── run_mesh.py                       chạy cả mesh theo thứ tự
```

## 4. Chạy

```powershell
.venv\Scripts\python phase6_data_mesh\run_mesh.py     # toàn bộ: ~23 giây
```

Hoặc từng bước, đúng vai từng team:
```powershell
# Team Sales
.venv\Scripts\python phase6_data_mesh\platform\ingest.py --domain sales
cd phase6_data_mesh\domains\sales\dbt;  ..\..\..\..\.venv\Scripts\dbt deps;  ..\..\..\..\.venv\Scripts\dbt build;  cd ..\..\..\..
# Team Logistics
.venv\Scripts\python phase6_data_mesh\platform\ingest.py --domain logistics
cd phase6_data_mesh\domains\logistics\dbt;  ..\..\..\..\.venv\Scripts\dbt deps;  ..\..\..\..\.venv\Scripts\dbt build;  cd ..\..\..\..
# Platform team + consumer
.venv\Scripts\python phase6_data_mesh\platform\validate_contracts.py
.venv\Scripts\python phase6_data_mesh\platform\catalog.py
.venv\Scripts\python phase6_data_mesh\consumers\exec_report.py
```

## 5. Điều cần quan sát (kết quả thật)

**① Cùng kết quả với warehouse trung tâm, nhưng mỗi phần có chủ:**

| Chỉ số | Phase 2 (trung tâm) | Phase 6 (mesh) | Lấy từ data product |
|---|---|---|---|
| Doanh thu đơn đã giao | 13,221,498.11 | **13,221,498.11** ✅ | `sales.orders` |
| Review: đúng hạn / trễ | 4.29 / 2.27 | **4.29 / 2.27** ✅ | `logistics.delivery_performance` (review lấy từ sales) |

Insight mới nhờ Logistics có vị trí seller: giao **liên bang** trung bình **15.1 ngày**, trễ 8.0%; **nội bang**
chỉ **7.9 ngày**, trễ 4.5%. Consumer JOIN 2 data product thấy RJ là bang doanh thu lớn thứ 2 nhưng trễ tới 12.1%.

**② Contract chặn thay đổi phá vỡ ngay tại domain Sales.** Ai đó "chỉ đổi tên một cột":
```
dbt build --vars "{simulate_breaking_change: true}"

This model has an enforced contract that failed.
| column_name             | definition_type | contract_type | mismatch_reason       |
| gross_merchandise_value | DOUBLE          |               | missing in contract   |
| items_value             |                 | DOUBLE        | missing in definition |
Done. PASS=3 WARN=0 ERROR=1 SKIP=3
```
→ Bảng `orders_v1` cũ **không bị ghi đè**, nên Logistics không bị gãy. Muốn đổi thật thì phải xuất bản
`orders_v2` song song, báo cho các consumer (có sẵn trong danh sách `consumers`), và chỉ xoá v1 khi họ đã chuyển xong.

**③ Governance tự động bắt vi phạm** (giả lập 2 tình huống làm ẩu, `validate_contracts.py` trả exit 1):
```
❌ đọc domain khác qua output port: sales_dp.staging.orders_v1: vi phạm, chỉ được đọc schema 'output'
❌ bảng thật khớp contract (11 cột): thừa ['customer_email']
❌ 2 vi phạm
```
Khi bình thường, mỗi data product qua 9–12 kiểm tra: đủ trường, đặt tên `_v1`, schema khớp, khoá chính, freshness
trong SLA, và chỉ đọc domain khác qua output port.

**④ Catalog**: ai cũng tra được data product nào tồn tại, của ai, liên hệ ai, bao nhiêu dòng,
xuất bản lúc nào, phụ thuộc gì, ai đang dùng.

**⑤ Lỗi thật gặp khi làm:** đặt staging là `access: private` thì dbt báo lỗi, vì `private` bắt buộc phải khai
báo *group*. Mức đúng là `protected`: chỉ dùng được trong chính project đó. Đây cũng là cách dbt hỗ trợ ý
"bảng nội bộ" của Data Mesh.

## 6. Trung tâm và Mesh: khi nào dùng cái nào?

| | Warehouse trung tâm (phase 1–4) | Data Mesh (phase 6) |
|---|---|---|
| Hợp với | Công ty nhỏ/vừa, ít nguồn, 1 team data | Công ty lớn, nhiều domain, nhiều team data |
| Ưu | Đơn giản, nhất quán, ít trùng lặp | Mở rộng theo số team, người hiểu nghiệp vụ làm data |
| Nhược | Team data thành nút cổ chai | Phức tạp: cần platform, governance, kỷ luật contract |
| Chi phí khởi đầu | Thấp | Cao |

> Data Mesh **không thay thế** những gì học ở phase 1–4. **Bên trong** mỗi domain vẫn là ELT, star schema,
> dbt, orchestration. Mesh chỉ thêm **ranh giới sở hữu** và **hợp đồng giữa các domain**.

## 7. Gợi ý khi áp dụng vào đồ án

1. **Xác định domain** theo nghiệp vụ, không theo công nghệ (Sales, Logistics, chứ không phải "team Postgres").
2. **Mỗi domain một data product đầu tiên**, có contract kiểu `data_product.yml`: owner, schema, SLA, version, consumers.
3. **Output port tách khỏi bảng nội bộ** (schema `output` + dbt `access: public` và `contract: enforced`).
4. **Platform tối thiểu**: một công cụ ingest chung, một bộ luật chung kiểm tra tự động, một catalog.
5. Nếu cần thêm: mỗi domain một Dagster code location (phase 4), một catalog thật (DataHub/OpenMetadata),
   và tách thành nhiều repo, mỗi team một repo.

## 8. Câu hỏi tự kiểm tra

1. Vì sao Logistics không tự ingest bảng `customers` để lấy bang của khách, mà phải đọc qua `sales.orders`?
   <details><summary>Đáp án</summary>Vì Sales sở hữu và hiểu data khách hàng, kể cả cái bẫy customer_id hay việc gộp theo người thật. Logistics tự ingest thì phải hiểu lại toàn bộ, dễ hiểu sai, và hai bên ra hai con số khác nhau. Dùng data product thì có một nguồn sự thật, có người chịu trách nhiệm.</details>
2. Sales muốn đổi `items_value` thành `gross_merchandise_value`. Quy trình đúng là gì?
   <details><summary>Đáp án</summary>Tạo <code>orders_v2</code> (contract mới) chạy song song với <code>orders_v1</code>, báo cho các consumer trong danh sách <code>consumers</code>, đặt hạn ngừng v1, đợi Logistics và exec_report chuyển sang v2, rồi mới xoá v1. Giống hệt cách deprecate một REST API.</details>
3. Nếu không có `validate_contracts.py`, mesh sẽ "mục" thế nào sau 1 năm với 20 domain?
   <details><summary>Đáp án</summary>Mỗi domain đặt tên một kiểu, có domain lén đọc bảng nội bộ của nhau (gãy khi bên kia refactor), contract không còn khớp bảng thật, không ai biết data cũ hay mới. Governance phải "computational" (bằng code, tự động), vì luật chỉ nằm trên giấy thì không ai tuân theo.</details>
4. Data Mesh có phải là "mỗi team tự làm gì thì làm" không?
   <details><summary>Đáp án</summary>Không. Domain tự do bên trong (model thế nào, dùng SQL gì), nhưng phải tuân luật chung ở ranh giới: contract, versioning, output port, SLA. Tự chủ có kỷ luật, đúng như microservices tự do bên trong nhưng phải giữ API contract.</details>
