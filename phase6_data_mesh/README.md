# Phase 6: Data Mesh

## Tóm tắt trong 1 câu

**Mỗi domain là một "phase 3 thu nhỏ" (EL → raw → staging → output) chạy trên warehouse riêng. Domain này
chỉ được đọc output của domain kia, và platform cung cấp đồ nghề cũng như kiểm tra luật cho tất cả.**

```
                    ┌────────── PLATFORM (đồ nghề dùng chung) ──────────┐
                    │ ingest.py · macro dbt · luật (policies) · catalog  │
                    └────────────────────────────────────────────────────┘
                            │ domain tự dùng            │ kiểm tra tất cả
                            ▼                           ▼
Postgres ──EL (ingest.py)──▶ sales.duckdb
(nguồn)                     raw ─dbt─▶ staging ─dbt─▶ output.orders_v1 ──┐
   │                                                      (data product) │ đọc read-only
   │                                                                     ▼
   └──EL (ingest.py)──▶ logistics.duckdb
                        raw ─dbt─▶ staging ─dbt─▶ output.delivery_performance_v1
                                                                     │
                                       exec_report.py (consumer) ◀───┘ đọc output của cả 2
```

## Vì sao cần Data Mesh?

Phase 1–4 có **một warehouse trung tâm, một team data làm cho mọi bộ phận**. Công ty nhỏ thì ổn. Công ty có
30 bộ phận thì team data thành **nút cổ chai**, lại **hiểu sai nghiệp vụ** (nhớ cái bẫy `customer_id` ở phase 0:
chỉ người làm bán hàng mới biết).

Data Mesh: **giao data về cho bộ phận hiểu nó nhất**. Dân SE cứ nghĩ là **monolith → microservices**:

| Microservices | Data Mesh | Trong project |
|---|---|---|
| Service | **Domain** | `domains/sales`, `domains/logistics` |
| Code private bên trong | Bảng nội bộ | `raw.*`, `staging.*` |
| Public API | **Data product** (output port) | `output.orders_v1` |
| OpenAPI spec | **Data contract** | `data_product.yml` |
| Team DevOps (K8s, CI) | **Platform** | `platform/` |

Data Mesh là cách **chia trách nhiệm giữa người với người**, không phải tool mới. Bên trong mỗi domain vẫn là
dbt, DuckDB như phase 3.

## Hỏi đáp: những chỗ dễ rối

### 1. Đây là mô phỏng à? Ngoài đời thư mục domain đâu có nằm chung?

**Đúng, đây là demo.** Mình gom vào một thư mục cho bạn chạy được trên một máy. Ngoài đời:

| Trong demo | Ngoài đời |
|---|---|
| `domains/sales/` | **Repo riêng** của team Sales, team đó tự sửa và tự deploy |
| `domains/logistics/` | **Repo riêng** của team Logistics |
| `platform/` | **Repo riêng** của team Platform |
| `run_mesh.py` chạy tuần tự | Mỗi team **tự lập lịch** (ví dụ mỗi team một Dagster như phase 4): Sales 02:00, Logistics 03:00 |

Ý hay bị hiểu nhầm: **Data Mesh tách về quyền sở hữu, không bắt buộc tách về máy móc.** Nhiều công ty vẫn dùng
chung **một** Snowflake/BigQuery, mỗi domain có database riêng và quyền truy cập riêng. Quan trọng là **ai chịu
trách nhiệm cho data**, chứ không phải data nằm trên máy nào.

### 2. Luồng dbt là raw → staging → output? Raw nằm ở đâu?

Đúng luồng đó:
```
raw  ──(dbt)──▶  staging  ──(dbt)──▶  output
data thô         làm sạch,            data product
copy từ nguồn    đổi tên, ép kiểu     công khai cho domain khác dùng
```

**Raw nằm trong file warehouse của chính domain đó**, schema `raw`:
- Sales: `warehouse/mesh/sales.duckdb` → `raw.orders`, `raw.customers`, ...
- Logistics: `warehouse/mesh/logistics.duckdb` → `raw.orders`, `raw.sellers`, ...

dbt **không tạo** raw, chỉ **đọc** raw (khai báo là `source` trong `_sources.yml`). Raw do bước EL đổ vào (câu 3).

Logistics có thêm **source thứ hai**: bảng `output.orders_v1` của Sales, mở **chỉ đọc** (xem
[_sources.yml](domains/logistics/dbt/models/staging/_sources.yml) và `profiles.yml`). Logistics không copy data
của Sales mà đọc thẳng data product của Sales.

### 3. Hai domain xài chung Postgres hay DB riêng? dbt là T, vậy EL ở đâu?

Có **2 loại DB**, đừng gộp lại:

| | Là gì | Chung hay riêng? |
|---|---|---|
| **Postgres** | DB của app (OLTP), là **nguồn** | Demo **dùng chung**, vì Olist chỉ có một DB |
| **DuckDB** | **Warehouse** để phân tích | **Mỗi domain một file**: `sales.duckdb`, `logistics.duckdb` |

Ngoài đời nguồn cũng tách: Sales lấy từ DB của *order service*, Logistics lấy từ DB của *shipping service*.

**EL là [platform/ingest.py](platform/ingest.py).** Gần giống `el_raw.py` ở phase 3, khác 2 điểm:
- Nó **không tự quyết** copy gì, mà đọc `domains/<domain>/ingest.yml` do domain tự khai báo.
- Nó **chỉ copy đúng cột đã khai báo**. Logistics không khai báo thông tin khách hàng nên không nhận được.

```
python platform/ingest.py --domain sales
   = E: đọc Postgres  +  L: ghi vào sales.duckdb/raw.*
```

### 4. Platform nằm ở đâu, ai dùng?

**Platform = bộ đồ nghề dùng chung**, do một **team Platform nhỏ** viết. Domain **tự lấy ra dùng**
(self-serve), không phải nhờ ai. Giống team DevOps dựng sẵn K8s, CI template, còn team service chỉ viết config.

| Trong `platform/` | Ai dùng | Ngoài đời thường là |
|---|---|---|
| `ingest.py` | **Domain**: viết `ingest.yml` rồi gọi | Airbyte, Fivetran |
| `dbt_platform/` (macro chung) | **Domain**: khai báo trong `packages.yml` | Thư viện nội bộ, như npm package của công ty |
| `policies.yml` + `validate_contracts.py` | **Platform** chạy tự động, kiểm tra mọi domain | Bước CI: sai luật thì không được merge |
| `catalog.py` | **Người dùng data** (consumer) | Trang catalog kiểu DataHub: có data product nào, của ai, mới hay cũ |

## Chạy

```powershell
.venv\Scripts\python phase6_data_mesh\run_mesh.py     # cả mesh, khoảng 23 giây
```

Script chạy lần lượt: ingest Sales → dbt Sales → ingest Logistics → dbt Logistics → kiểm tra luật → catalog →
báo cáo. Bước nào lỗi thì dừng.

## Quan sát được gì

**1. Số liệu khớp warehouse trung tâm** (phase 2): doanh thu 13,221,498.11; review đúng hạn 4.29, trễ 2.27.
Khác ở chỗ giờ mỗi con số **có chủ**: doanh thu thuộc Sales, giao hàng thuộc Logistics.

**2. Insight mới:** giao **liên bang** trung bình 15.1 ngày (trễ 8.0%), **nội bang** chỉ 7.9 ngày (trễ 4.5%).
JOIN 2 data product thấy RJ doanh thu lớn thứ 2 nhưng trễ tới 12.1%.

**3. Contract chặn thay đổi phá vỡ.** Sales "chỉ đổi tên một cột" `items_value` thì dbt từ chối build:
```
dbt build --vars "{simulate_breaking_change: true}"

This model has an enforced contract that failed.
| gross_merchandise_value | DOUBLE |        | missing in contract   |
| items_value             |        | DOUBLE | missing in definition |
```
Bảng `orders_v1` cũ giữ nguyên, Logistics không gãy. Muốn đổi thật thì làm `orders_v2` chạy song song, báo các
consumer, đợi họ chuyển xong mới xoá v1. Y hệt deprecate REST API.

**4. Governance bắt người làm ẩu.** Giả lập Logistics lén đọc bảng nội bộ của Sales, và ai đó thêm cột ngoài
contract:
```
❌ sales_dp.staging.orders_v1: vi phạm, chỉ được đọc schema 'output'
❌ bảng thật khớp contract (11 cột): thừa ['customer_email']
```

## Trung tâm hay Mesh?

- **Công ty nhỏ, một team data** → warehouse trung tâm (phase 1–4). Đơn giản, rẻ.
- **Công ty lớn, nhiều bộ phận** → Mesh. Mở rộng được, nhưng tốn công dựng platform và giữ kỷ luật contract.

## Áp dụng vào đồ án

1. Chia domain **theo nghiệp vụ** (Sales, Logistics), không theo công nghệ.
2. Mỗi domain **một data product đầu tiên** có contract: owner, schema, SLA, version, ai đang dùng.
3. Tách **output** (công khai) khỏi **raw/staging** (nội bộ).
4. Platform tối thiểu: **một tool ingest, một bộ luật kiểm tra tự động, một catalog**.

File nên đọc: [data_product.yml của Sales](domains/sales/data_product.yml) (contract trông thế nào),
[policies.yml](platform/policies.yml) (luật chung).

## Câu hỏi tự kiểm tra

1. Vì sao Logistics không tự ingest bảng `customers`, mà đọc qua data product của Sales?
   <details><summary>Đáp án</summary>Sales mới hiểu data khách hàng (kể cả bẫy customer_id). Logistics tự làm thì dễ hiểu sai, hai bên ra hai con số khác nhau. Dùng data product thì chỉ có một nguồn sự thật, có người chịu trách nhiệm.</details>
2. Sales muốn đổi tên cột `items_value`. Làm sao cho đúng?
   <details><summary>Đáp án</summary>Làm <code>orders_v2</code> song song với v1, báo consumer, đợi họ chuyển xong mới xoá v1.</details>
3. Không có `validate_contracts.py` thì sau 1 năm, 20 domain sẽ ra sao?
   <details><summary>Đáp án</summary>Mỗi domain đặt tên một kiểu, lén đọc bảng nội bộ của nhau, contract không còn khớp bảng thật. Luật chỉ nằm trên giấy thì không ai theo, nên phải kiểm tra bằng code.</details>
4. Data Mesh có phải "mỗi team tự làm gì thì làm"?
   <details><summary>Đáp án</summary>Không. Bên trong tự do, nhưng ở ranh giới (contract, version, output) phải theo luật chung. Giống microservices: code bên trong tuỳ team, API phải giữ đúng.</details>
