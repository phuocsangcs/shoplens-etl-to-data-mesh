# Phase 3: ELT với dbt

## 1. Khái niệm (5 phút)

### ETL và ELT: chỉ đảo chữ T và L, nhưng khác cả cách làm

```
ETL (phase 1-2):  Postgres ──E──▶ pandas (T, ngoài warehouse) ──L──▶ warehouse: chỉ có data ĐÃ sạch
ELT (phase 3):    Postgres ──E──▶ ──L──▶ warehouse: raw (thô) ──T bằng SQL, TRONG warehouse──▶ staging ──▶ marts
```

| | ETL | ELT |
|---|---|---|
| Data thô | Bị bỏ sau khi transform | **Luôn còn** trong schema `raw` |
| Đổi quy tắc làm sạch | Phải extract lại từ nguồn | Sửa SQL, chạy lại dbt, xong |
| Sức tính toán | RAM của 1 máy chạy Python | Sức mạnh của warehouse (Snowflake scale lên hàng nghìn CPU) |
| Ngôn ngữ transform | Python + SQL lẫn lộn | **Chỉ SQL**, analyst cũng tự viết được |

Ngành chuyển sang ELT khi cloud warehouse (Snowflake, BigQuery) đủ mạnh và đủ rẻ.

### dbt là gì?

**dbt** (data build tool) là tool lo chữ **T** của ELT. Bạn viết mỗi bảng là **một file `SELECT`**,
dbt lo phần còn lại: tạo bảng/view, chạy đúng thứ tự, chạy test, sinh tài liệu.
Có thể hình dung dbt là **"framework cho SQL"**, giống Spring/Express cho backend.

| Khái niệm dbt | Là gì | Thay cho cái gì ở phase 1-2 |
|---|---|---|
| **model** | 1 file `.sql` chứa 1 câu `SELECT` = 1 bảng/view | `transform.py`, `sql/0X_*.sql` |
| **source** | Khai báo bảng thô: `{{ source('olist','orders') }}` | Viết cứng tên bảng |
| **ref** | Tham chiếu model khác: `{{ ref('stg_orders') }}`. dbt tự suy ra **thứ tự chạy (DAG)** | Tự đánh số `01_`, `02_`… |
| **materialization** | Lưu model dạng gì: `view`, `table`, `incremental` | `CREATE OR REPLACE TABLE` tự viết |
| **test** | Khai báo trong YAML: `unique`, `not_null`, `relationships`… | Dict `CHECKS` trong `build_star.py` |
| **seed** | File CSV nhỏ do người duy trì, nạp thành bảng | Dict `MISSING_TRANSLATIONS` |
| **macro** | "Hàm" SQL tái sử dụng (Jinja) | Hàm `normalize_city()` Python |
| **snapshot** | Tự động làm **SCD Type 2** | *(chưa có, mới)* |
| **incremental** | Chỉ xử lý dữ liệu mới | Watermark tự viết ở phase 1 |
| **docs** | Website tài liệu + sơ đồ lineage | *(chưa có, mới)* |

## 2. Luồng

```
 Postgres ──el_raw.py──▶ raw.*          (9 bảng, y nguyên + cột _loaded_at)
 (nguồn)   DuckDB ATTACH    │
                            ▼  ┌──────────────────── dbt build ─────────────────────┐
                    staging.stg_*        làm sạch 1-1 với nguồn (VIEW)
                            │            ← seeds.category_translation_fixes
                            ▼
              intermediate.int_customer_latest_address   1 người = 1 địa chỉ hiện tại
                            │
                            ▼
              snapshots.snap_customer_address   ← SCD2: chụp lại mỗi lần chạy, giữ lịch sử
                            │
                            ▼
                    marts.dim_* / fact_*   star schema (TABLE; fact_order_items: INCREMENTAL)
                            │
                            ▼
                    37 test tự động       test fail → model phía sau dừng lại
                               └────────────────────────────────────────────────────┘
```

Warehouse riêng cho phase này: `warehouse/shoplens_elt.duckdb` (không đụng file của phase 1-2).

### Cấu trúc dbt project ([shoplens/](shoplens/))

```
shoplens/
├── dbt_project.yml          cấu hình: tầng nào lưu dạng gì, vào schema nào
├── profiles.yml             kết nối warehouse (đổi sang Snowflake chỉ sửa file này)
├── macros/                  normalize_city, generate_schema_name
├── seeds/                   category_translation_fixes.csv
├── models/
│   ├── staging/             _sources.yml, _staging.yml (test), stg_*.sql
│   ├── intermediate/        int_customer_latest_address.sql
│   └── marts/               _marts.yml (test + docs), dim_*.sql, fact_*.sql
├── snapshots/               snap_customer_address.yml (SCD2)
└── tests/                   2 singular test tự viết bằng SQL
```

## 3. Chạy

> ⚠️ **Windows:** dbt đọc file bằng bảng mã cp1252, gặp tiếng Việt trong comment là lỗi.
> Luôn đặt `PYTHONUTF8=1` trước (Git Bash: `export PYTHONUTF8=1`, PowerShell: `$env:PYTHONUTF8=1`).

```bash
export PYTHONUTF8=1
.venv/Scripts/python phase3_dbt/el_raw.py          # EL: Postgres → raw (~2 giây)
cd phase3_dbt/shoplens
../../.venv/Scripts/dbt build                      # seed + models + snapshot + test, đúng thứ tự
../../.venv/Scripts/dbt docs generate              # sinh tài liệu
../../.venv/Scripts/dbt docs serve                 # mở http://localhost:8080 → bấm icon lineage góc dưới phải
```

Các lệnh dbt hay dùng khác: `dbt run` (chỉ model), `dbt test` (chỉ test), `dbt build -s fact_orders+`
(chạy fact_orders và mọi thứ phía sau nó), `dbt build -s +fact_orders` (và mọi thứ phía trước).

**Demo SCD2: 500 khách chuyển nhà SP → RJ:**
```bash
cd ../..
.venv/Scripts/python phase3_dbt/simulate_address_changes.py   # app UPDATE đè địa chỉ trong Postgres
.venv/Scripts/python phase3_dbt/el_raw.py                     # nạp lại raw
(cd phase3_dbt/shoplens && ../../.venv/Scripts/dbt build)     # snapshot phát hiện thay đổi
.venv/Scripts/python phase3_dbt/compare_scd.py                # so sánh SCD1 vs SCD2
# Hoàn tác nguồn: .venv/Scripts/python phase0_source/load_olist.py
```

## 4. Điều cần quan sát (kết quả thật)

**① Cùng kết quả với phase 1+2, nhưng gọn hơn nhiều**

| | Phase 1+2 (ETL) | Phase 3 (ELT + dbt) |
|---|---|---|
| Doanh thu delivered | 13,221,498.11 | **13,221,498.11** ✅ |
| Tỉ lệ khách quay lại | 3.12% | **3.12%** ✅ |
| Thời gian EL / build | ~11s ETL + ~1s build | **~2s EL + ~4.6s dbt build** |
| Thứ tự chạy | Tự viết trong `pipeline.py` + đánh số file | **dbt tự suy ra** từ `ref()` |
| Test | Tự viết 10 check bằng Python | **37 test** khai báo YAML + 2 SQL |
| Tài liệu, lineage | Không có | `dbt docs` |

**② SCD Type 2 hoạt động**: một người sau khi chuyển nhà có 2 dòng trong `dim_customer`:

| customer_key | city | state | valid_from | valid_to | is_current |
|---|---|---|---|---|---|
| d6ec55d366… | charqueada | SP | 1900-01-01 | 2026-11-20 15:43 | false |
| e16bac7752… | rio de janeiro | RJ | 2026-11-20 15:43 | 9999-12-31 | true |

Doanh thu lịch sử theo bang sau khi 500 người chuyển đi:

| Bang | SCD1 (theo địa chỉ hiện tại) | SCD2 (theo địa chỉ lúc mua) | Chênh lệch |
|---|---|---|---|
| SP | 5,141,625 | **5,205,024** | −63,400 |
| RJ | 1,887,353 | **1,823,953** | +63,400 |

→ SCD1 "dời" 63,400 BRL doanh thu **quá khứ** từ SP sang RJ, tức là lịch sử bị viết lại. SCD2 giữ đúng.
Cả hai đều có ích tuỳ câu hỏi: *"khách hiện ở đâu?"* (dùng `is_current`) hay *"bán được bao nhiêu ở đâu?"* (dùng `customer_key` của fact).

**③ Surrogate key bằng hash**: `md5(product_id)`, `dbt_scd_id`. Phase 2 dùng `ROW_NUMBER()`, số bị đổi mỗi lần dựng lại,
nên fact cũ (incremental, không dựng lại) sẽ trỏ sai. Hash thì cùng input luôn ra cùng key.

**④ Bài học thật gặp khi làm:** lần đầu chỉ 499/500 người có lịch sử. Nguyên nhân: có người đặt 2 đơn
**cùng một giây**. Postgres (`DISTINCT ON`) chọn ngẫu nhiên một dòng, dbt chọn theo `customer_id`, nên hai bên chọn lệch nhau.
Đã sửa bằng cách thêm `customer_id` vào `ORDER BY` ở cả hai nơi. **Mọi phép "lấy dòng mới nhất" phải có tie-breaker**,
nếu không mỗi lần chạy ra một kết quả (*non-deterministic*).

## 5. Điểm yếu còn lại (lý do có phase 4, 5)

1. **Ai bấm nút?** Hiện phải tự gõ `el_raw.py` rồi `dbt build`. Quên chạy thì data cũ; chạy `dbt` trước `el_raw` thì sai.
   Cần **orchestrator** lập lịch + quản lý phụ thuộc giữa EL và dbt (phase 4).
2. **Snapshot chỉ chính xác bằng tần suất chạy.** Khách đổi địa chỉ 2 lần trong 1 ngày mà mỗi ngày chạy 1 lần
   thì mất phiên bản ở giữa. Muốn chính xác tuyệt đối thì cần CDC.
3. **Test mới chỉ kiểm tra cấu trúc** (unique, not_null). Chưa kiểm tra *data có tươi không*, *số có hợp lý không*
   (doanh thu tháng 9/2018 chỉ còn 16 đơn mà không ai cảnh báo). Đó là phase 5.

## 6. Câu hỏi tự kiểm tra

1. Sếp đổi quy tắc: "giữ review **đầu tiên** của mỗi đơn, không phải mới nhất". Ở phase 1 và phase 3 phải làm gì?
   <details><summary>Đáp án</summary>Phase 1: sửa transform.py rồi chạy <code>--full-refresh</code> để extract lại toàn bộ từ Postgres. Phase 3: đổi <code>desc</code> thành <code>asc</code> trong <code>stg_order_reviews.sql</code>, chạy <code>dbt build</code>. Raw vẫn còn nên không đụng tới nguồn.</details>
2. Vì sao staging là `view` còn marts là `table`?
   <details><summary>Đáp án</summary>Staging chỉ là bước trung gian, không ai query trực tiếp. View không tốn chỗ và luôn phản ánh raw mới nhất. Marts thì analyst/dashboard query liên tục, nên tính sẵn thành table để đọc nhanh.</details>
3. Nếu xoá snapshot rồi chạy lại `dbt build`, lịch sử SCD2 có tự quay lại không?
   <details><summary>Đáp án</summary>Không. Snapshot là thứ duy nhất trong dbt <b>không thể dựng lại</b> từ raw, vì nguồn (OLTP) đã ghi đè và không còn giữ lịch sử. Mất snapshot là mất lịch sử vĩnh viễn. Vì vậy snapshot phải được backup cẩn thận.</details>

---
⏭️ **Phase 4**: dùng **Dagster** ghép `el_raw` và `dbt build` thành một pipeline có lịch chạy, phụ thuộc, retry.
