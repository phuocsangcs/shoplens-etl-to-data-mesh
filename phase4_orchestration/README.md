# Phase 4: Orchestration với Dagster

## 1. Khái niệm (5 phút)

Đến phase 3, pipeline vẫn cần **người bấm nút**: chạy `el_raw.py` trước rồi mới `dbt build`. Quên thì data cũ,
chạy ngược thứ tự thì data sai, nguồn sập lúc 2 giờ sáng thì sáng hôm sau mới biết.

**Orchestrator** là "người quản đốc" của pipeline:

| Việc | Không có orchestrator | Có orchestrator |
|---|---|---|
| Chạy theo lịch | Tự nhớ / cron | `cron_schedule="0 2 * * *"` |
| Thứ tự | Tự đảm bảo EL xong mới dbt | Khai báo phụ thuộc, tự sắp xếp |
| Bước trước fail | Bước sau vẫn chạy trên data cũ/hỏng | **Bước sau không chạy** |
| Lỗi tạm thời | Ai đó chạy lại bằng tay | **Tự retry** |
| Theo dõi | Đọc log rải rác | Giao diện web: lịch sử run, thời gian, lỗi, metadata |

> **Sao không dùng cron?** Cron chỉ biết "đến giờ thì chạy lệnh". Nó không biết lệnh A phụ thuộc lệnh B,
> không retry, không lưu lịch sử, không có giao diện xem lỗi.

**Dagster và Airflow:** Airflow (2014) là orchestrator phổ biến nhất, tư duy theo **task** ("chạy bước này,
rồi bước kia"). Dagster (2019) tư duy theo **asset** ("bảng này cần tồn tại và được cập nhật"), rất hợp
với data warehouse. Hiểu một cái thì học cái kia nhanh.

| Khái niệm Dagster | Ý nghĩa | Trong project |
|---|---|---|
| **Asset** | Một "thứ" dữ liệu tồn tại lâu dài (bảng, file) | `olist/orders`, `marts/fact_orders`, `daily_kpi_report` |
| **Materialize** | Tạo hoặc cập nhật asset | Chạy EL, chạy dbt, ghi CSV |
| **Dependency** | Asset B cần asset A | `stg_orders` cần `olist/orders` |
| **Asset check** | Kiểm tra chất lượng gắn với asset | 36 dbt test được hiển thị thành check |
| **Job** | Nhóm asset chạy cùng nhau | `daily_refresh` = tất cả |
| **Schedule** | Chạy job theo lịch | 02:00 mỗi ngày (giờ VN) |
| **RetryPolicy** | Thử lại khi lỗi | EL: 3 lần, chờ 5s → 10s → 20s |

## 2. Luồng

```
                    ┌──────────────── Dagster: job daily_refresh (02:00 mỗi ngày) ────────────────┐
                    │                                                                              │
 Postgres ─────▶ [ingestion]          [staging] → [intermediate] → [snapshots] → [marts]  ─────▶ [reporting]
                 olist/* (9 asset)     dbt build: mỗi model = 1 asset, mỗi test = 1 check          daily_kpi_report
                 Python (el_raw.py)    (dagster-dbt đọc manifest của dbt project phase 3)          → monthly_kpi.csv
                 retry 3 lần                                                                       Python đọc marts
                    │                                                                              │
                    └─── fail ở đâu → mọi asset phía sau KHÔNG chạy, warehouse giữ data tốt cũ ───┘
```

**Điểm hay:** asset key `olist/orders` trùng với `source('olist', 'orders')` trong dbt, nên Dagster **tự nối**
bảng raw do Python tạo với model dbt dùng nó. Toàn bộ lineage từ Postgres đến file báo cáo nằm trên **một sơ đồ**.

File duy nhất: [definitions.py](definitions.py). Code EL tái sử dụng hàm `extract_load()` từ
[phase3_dbt/el_raw.py](../phase3_dbt/el_raw.py), không viết lại.

## 3. Chạy

**Giao diện web** (PowerShell, từ thư mục gốc project):
```powershell
New-Item -ItemType Directory -Force .dagster_home | Out-Null
$env:DAGSTER_HOME = "$PWD\.dagster_home"          # nơi Dagster lưu lịch sử run
.venv\Scripts\dagster dev -f phase4_orchestration\definitions.py
# mở http://localhost:3000
```

Trên giao diện, nên xem lần lượt:
1. **Assets → View lineage**: sơ đồ 29 asset, chia 7 nhóm (ingestion, seeds, staging, intermediate, snapshots, marts, reporting).
2. Bấm **Materialize all**, rồi mở run vừa tạo để xem từng bước chạy theo thời gian thực (biểu đồ Gantt).
3. Bấm vào `marts/fact_orders` → tab **Checks**: kết quả các dbt test.
4. Bấm vào `daily_kpi_report` → metadata có **bảng preview** 6 tháng gần nhất.
5. **Automation → daily_schedule**: bật/tắt lịch chạy (mặc định tắt).

**Không giao diện:**
```powershell
$env:DAGSTER_HOME = "$PWD\.dagster_home"
.venv\Scripts\dagster job execute -f phase4_orchestration\definitions.py -j daily_refresh
```

> Schedule chỉ chạy khi có **dagster-daemon** đang sống (`dagster dev` đã bật sẵn daemon). Ở production,
> daemon và webserver chạy như service trên server (hoặc dùng Dagster Cloud).

## 4. Điều cần quan sát (kết quả thật)

**① Chạy thành công:** `SUCCESS` · 3 bước · **29 asset** được materialize · **36 asset check** · khoảng 30–40 giây.
File [warehouse/reports/monthly_kpi.csv](../warehouse/reports/monthly_kpi.csv) được tạo:
```
year_month,orders,revenue_brl,avg_review,pct_late
2018-06,6099,856077.86,4.31,1.2
2018-07,6159,867953.46,4.32,3.4
2018-08,6351,838576.64,4.31,6.2
```

**② Nguồn sập hẳn** (tắt Postgres bằng `docker stop`):
```
  +  9.3s STEP_START         olist_raw_tables
  + 17.7s STEP_UP_FOR_RETRY  olist_raw_tables     ← lần 1 lỗi, chờ 5s
  + 27.2s STEP_RESTARTED     olist_raw_tables
  + 35.6s STEP_UP_FOR_RETRY  olist_raw_tables     ← lần 2 lỗi, chờ 10s
  + 54.7s STEP_RESTARTED     olist_raw_tables
  + 63.1s STEP_UP_FOR_RETRY  olist_raw_tables     ← lần 3 lỗi, chờ 20s
  +102.1s STEP_RESTARTED     olist_raw_tables
  +110.4s STEP_FAILURE       olist_raw_tables     ← bỏ cuộc → run FAILURE
                                                     dbt và report KHÔNG chạy
```
→ Marts vẫn giữ data tốt của lần chạy trước. **Không bao giờ build đè bằng data hỏng.**

**③ Nguồn sập tạm thời** (tắt Postgres 35 giây rồi bật lại):
```
  +  7.7s STEP_START         olist_raw_tables
  + 16.9s STEP_UP_FOR_RETRY  olist_raw_tables     ← lần 1 lỗi
  + 25.6s STEP_RESTARTED     olist_raw_tables
  + 33.6s STEP_SUCCESS       olist_raw_tables     ← nguồn đã sống lại, thành công
  + 37.3s STEP_START         shoplens_dbt_assets
  + 48.7s STEP_SUCCESS       shoplens_dbt_assets
  + 53.2s STEP_SUCCESS       daily_kpi_report     ← run SUCCESS, không ai phải can thiệp
```

**④ Lỗi thật gặp khi làm:**
- Chạy bằng dòng lệnh thì OK, nhưng trong `dagster dev` lại báo *"dbt executable not found on PATH"*. Nguyên nhân:
  `dagster dev` gọi `dbt parse` qua PATH, mà venv chưa được activate. Đã sửa bằng cách thêm `.venv/Scripts` vào PATH
  ngay đầu `definitions.py`. Bài học: **môi trường lúc dev và lúc orchestrator chạy thường khác nhau** (PATH, biến
  môi trường, thư mục làm việc). Đây là nguồn lỗi kinh điển khi đưa pipeline lên server.
- 37 dbt test nhưng chỉ 36 check: test `assert_revenue_reconciles_with_raw` dùng tới 2 thứ (fact và source),
  nên Dagster không gắn được vào một asset duy nhất. Test này vẫn chạy trong `dbt build` (PASS=56).

## 5. Còn thiếu gì (lý do có phase 5)

Pipeline giờ **chạy đúng giờ, đúng thứ tự, tự phục hồi**. Nhưng "chạy thành công" chưa chắc là "data đúng":
- Tháng 2018-09 chỉ có 16 đơn (nỗi đau #5 từ phase 0) mà pipeline vẫn báo **SUCCESS** xanh lè.
- Nếu nguồn không sập mà chỉ ngừng cập nhật (data cũ 3 ngày), cũng không ai biết.
- Test hiện tại chỉ kiểm tra **cấu trúc** (unique, not_null), chưa kiểm tra **nghiệp vụ** (doanh thu hợp lý không?).

## 6. Câu hỏi tự kiểm tra

1. Vì sao retry chỉ đặt cho bước EL mà không đặt cho dbt?
   <details><summary>Đáp án</summary>Retry chỉ có ích với lỗi <b>tạm thời</b> (mạng, nguồn bận), mà bước EL đi qua mạng tới hệ thống khác nên hay gặp loại lỗi này. dbt fail thường do SQL sai hoặc test fail (data hỏng): thử lại 3 lần vẫn fail y vậy, chỉ tốn thời gian. Retry lỗi <b>vĩnh viễn</b> là vô ích.</details>
2. Nếu bỏ phụ thuộc giữa `olist/*` và dbt (cho chạy song song) thì chuyện gì có thể xảy ra?
   <details><summary>Đáp án</summary>dbt có thể đọc raw khi EL mới copy được một nửa: orders đã mới nhưng order_items còn cũ, fact bị lệch. Hoặc EL fail mà dbt vẫn build, dashboard hiển thị data cũ nhưng trông như mới.</details>
3. Dagster tư duy theo "asset", Airflow theo "task". Asset có lợi gì khi nói về Data Mesh (phase 6)?
   <details><summary>Đáp án</summary>Data Mesh xoay quanh <b>data product</b>, mà data product là các asset có chủ sở hữu. Tư duy asset giúp trả lời "bảng này của ai, cập nhật lúc nào, phụ thuộc gì" thay vì "script nào chạy lúc mấy giờ".</details>

---
⏭️ **Phase 5**: Data quality: kiểm tra freshness, kiểm tra nghiệp vụ, để pipeline biết khi nào data **sai** chứ không chỉ khi nào **lỗi**.
