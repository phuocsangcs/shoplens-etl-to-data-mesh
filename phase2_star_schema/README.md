# Phase 2: Star Schema (Dimensional Modeling)

## 1. Khái niệm (10 phút, phần quan trọng nhất của cả project)

Phase 1 đã **làm sạch** data, nhưng bảng vẫn giữ hình dạng của app (3NF). Phase này **mô hình hoá lại**
theo cách tối ưu cho *phân tích*: kỹ thuật **Dimensional Modeling** của Ralph Kimball (1996), đến giờ
vẫn là chuẩn của ngành.

Mọi câu hỏi phân tích đều có dạng: **"Đo *cái gì*, theo *góc nhìn* nào?"**
> "**Doanh thu** theo **tháng** và **category**"  ·  "**Số ngày giao** theo **bang**"

Vì vậy chia bảng làm 2 loại:

| | **FACT** (sự kiện) | **DIMENSION** (ngữ cảnh) |
|---|---|---|
| Chứa | **Measures**: con số cộng được (price, delivery_days) + khoá tới dim | **Thuộc tính mô tả** để lọc/nhóm (category, state, year) |
| Trả lời | "đo *cái gì*" | "theo *góc nhìn* nào" |
| Hình dạng | Dài (hàng triệu–tỷ dòng), hẹp | Ngắn, rộng (nhiều cột) |
| Ví dụ | `fact_order_items`, `fact_orders` | `dim_customer`, `dim_product`, `dim_date` |

Fact nằm giữa, các dim xếp quanh nên trông như **ngôi sao**:

```
                     dim_date
                        │
       dim_customer ─── FACT ─── dim_product
                        │
                    dim_seller
```

### Các thuật ngữ cần nắm

| Thuật ngữ | Ý nghĩa | Trong project |
|---|---|---|
| **Grain** ⭐ | *"Mỗi dòng của fact đại diện cho cái gì?"* Phải trả lời được bằng **một câu** trước khi viết SQL | `fact_order_items`: 1 món trong 1 đơn. `fact_payments`: 1 lần thanh toán. `fact_orders`: 1 đơn |
| **Measure** | Cột số trong fact, cộng/trung bình được | `price`, `freight_value`, `delivery_days` |
| **Surrogate key** | Khoá số nguyên do warehouse tự sinh, thay cho id của nguồn | `customer_key`, `product_key` |
| **Degenerate dimension** | Thuộc tính nằm ngay trong fact, không đáng làm bảng dim riêng | `order_id`, `order_status` |
| **Unknown member** | Dòng `key = -1` trong mỗi dim, để fact không bao giờ bị rơi khi JOIN | `dim_customer` có dòng `'unknown'` |
| **Conformed dimension** | Một dim dùng chung cho nhiều fact, nhờ vậy so sánh chéo được | `dim_customer` dùng cho cả 3 fact |
| **Phi chuẩn hoá** | Cố tình lặp dữ liệu (tên category nằm luôn trong dim_product) để bớt JOIN | Ngược với 3NF ở môn CSDL! |

### Quy trình 4 bước của Kimball (đã áp dụng ở đây)
1. **Chọn quy trình nghiệp vụ**: bán hàng, thanh toán, giao hàng
2. **Khai báo grain**: 1 món / 1 lần thanh toán / 1 đơn
3. **Chọn dimension**: ai (customer), cái gì (product), ai bán (seller), khi nào (date)
4. **Chọn measure**: tiền, phí ship, số ngày giao, điểm review

## 2. Mô hình đã dựng

```
                                ┌────────────────┐
                                │   dim_date     │ 1,096 ngày (2016–2018)
                                │ date_key PK    │ year, quarter, month,
                                │                │ is_weekend, is_black_friday
                                └───────┬────────┘
                                        │
┌────────────────┐    ┌─────────────────┴──────────────┐    ┌────────────────┐
│ dim_customer   │    │ fact_order_items  (112,650)    │    │ dim_product    │
│ customer_key PK├────┤ grain: 1 món trong 1 đơn       ├────┤ product_key PK │
│ customer_      │    │ order_date_key, customer_key,  │    │ category (EN)  │
│   unique_id    │    │ product_key, seller_key        │    │ category_pt    │
│ city, state    │    │ price, freight_value           │    │ weight_class   │
│ order_count    │    └────────────────────────────────┘    └────────────────┘
│ is_repeat_     │    ┌────────────────────────────────┐    ┌────────────────┐
│   customer     ├────┤ fact_payments     (103,883)    │    │ dim_seller     │
│ (96,096 người) │    │ grain: 1 lần thanh toán        │    │ seller_key PK  │
│                │    │ payment_type, payment_value    │    │ city, state,   │
│                │    └────────────────────────────────┘    │ lat, lng       │
│                │    ┌────────────────────────────────┐    └────────────────┘
│                ├────┤ fact_orders       (99,441)     │
└────────────────┘    │ grain: 1 đơn (vòng đời đơn)    │
                      │ items_value, payment_value,    │
                      │ delivery_days, is_late,        │
                      │ review_score                   │
                      └────────────────────────────────┘
```

**3 fact cho 3 grain khác nhau.** Không bao giờ trộn 2 grain vào 1 bảng, vì đó chính là lỗi fan-out.

## 3. Luồng

```
clean.* (phase 1) ──build_star.py──▶ chạy sql/01..08 theo thứ tự ──▶ mart.* ──▶ 10 kiểm tra tự động
                                     (dim trước, fact sau vì fact                 ├ grain duy nhất?
                                      cần lookup surrogate key từ dim)            ├ khoá mồ côi?
                                                                                  └ tổng tiền khớp nguồn?
```

| File | Vai trò |
|---|---|
| [sql/01_dim_date.sql](sql/01_dim_date.sql) | Sinh lịch 2016–2018 kèm mọi thuộc tính ngày |
| [sql/02_dim_customer.sql](sql/02_dim_customer.sql) | ⭐ Gộp 99,441 `customer_id` thành 96,096 **người**, diệt bẫy #2 |
| [sql/03_dim_product.sql](sql/03_dim_product.sql) · [04_dim_seller.sql](sql/04_dim_seller.sql) | Dimension sản phẩm, seller |
| [sql/05_fact_order_items.sql](sql/05_fact_order_items.sql) | ⭐ Fact chính, đổi id nguồn thành surrogate key |
| [sql/06_fact_payments.sql](sql/06_fact_payments.sql) | Fact riêng cho thanh toán, diệt fan-out #3 |
| [sql/07_fact_orders.sql](sql/07_fact_orders.sql) | Tổng hợp lên grain đơn **trước** khi JOIN |
| [sql/08_snowflake_variant.sql](sql/08_snowflake_variant.sql) | Bản snowflake schema để so sánh |
| [build_star.py](build_star.py) | Chạy SQL + kiểm tra chất lượng mô hình |
| [analyze.py](analyze.py) | Trả lời câu hỏi business |

## 4. Chạy

```bash
.venv/Scripts/python phase2_star_schema/build_star.py   # dựng mart (vài giây) + 10 kiểm tra
.venv/Scripts/python phase2_star_schema/analyze.py      # câu hỏi business
```

## 5. Điều cần quan sát (kết quả thật)

**Nỗi đau phase 0 đã được diệt:**

| Nỗi đau | Phase 0 (trên Postgres) | Phase 2 (trên star schema) |
|---|---|---|
| #2 Bẫy customer_id | Phải biết dùng `customer_unique_id`, viết 2 CTE + JOIN | `AVG(is_repeat_customer)` trên **1 bảng, 0 JOIN** → **3.12%** ✅ |
| #3 Fan-out | JOIN payments thì doanh thu bị đội lên 13.81 triệu | Grain tách bạch, **không thể** JOIN nhầm → **13,221,498.11** ✅ khớp |
| #4 Query rối | 4 JOIN + LEFT JOIN + COALESCE | fact + 1–2 JOIN, không COALESCE |

**Insight business** (dễ hỏi nhờ mô hình tốt):
- 🚚 **Giao trễ thì review sụp**: đơn đúng hạn được 4.29 sao, đơn trễ chỉ **2.27 sao**, và **62.4%** đơn trễ bị chấm 1–2 sao (đơn đúng hạn là 9.3%).
- 🛍️ **Black Friday 2017**: 1,166 đơn/ngày, gấp khoảng **10 lần** ngày thường (121 đơn).
- 📍 Bang MA trễ 17.4%, CE 13.7%: vùng đông bắc xa kho, giao lâu hơn.
- 💳 Thẻ tín dụng chiếm khoảng 78% tiền thu, trả góp trung bình 3.5 kỳ.
- ⚠️ 2018-Q3 doanh thu thấp hẳn: không phải kinh doanh kém, mà data bị cắt (nỗi đau #5 vẫn còn, để phase 5).

**Star vs Snowflake:** cùng một kết quả, nhưng snowflake cần thêm 1 JOIN cho mọi query. Ngành dùng star là chủ yếu.

## 6. Còn thiếu gì (lý do có phase 3)

1. **Mất lịch sử**: `dim_customer` là **SCD Type 1**, thành phố bị ghi đè bằng địa chỉ mới nhất. Khách chuyển
   từ SP sang RJ thì toàn bộ doanh thu cũ của họ bị tính cho RJ. Cần **SCD Type 2** (phase 3).
2. **SQL rời rạc**: thứ tự chạy phải tự đánh số `01..08`, test phải tự viết bằng Python, không có tài liệu,
   không biết bảng nào phụ thuộc bảng nào. **dbt** sinh ra để giải đúng mấy việc này.
3. **Vẫn là ETL**: transform nằm rải ở 2 nơi (pandas ở phase 1, SQL ở phase 2). Phase 3 gom hết về SQL trong warehouse, tức là **ELT**.

## 7. Câu hỏi tự kiểm tra

1. Sếp muốn "**số đơn** theo category". Đếm `COUNT(*)` trên `fact_order_items` có đúng không?
   <details><summary>Đáp án</summary>Sai. Grain là "món", nên 1 đơn 3 món bị đếm 3 lần. Phải dùng <code>COUNT(DISTINCT order_id)</code>. Luôn hỏi "grain là gì?" trước khi tổng hợp.</details>
2. Vì sao `fact_orders` tổng hợp items và payments **trong CTE riêng rồi mới JOIN**, chứ không JOIN thẳng rồi `SUM`?
   <details><summary>Đáp án</summary>JOIN thẳng items × payments sẽ fan-out: đơn 2 món × 2 lần thanh toán thành 4 dòng, SUM bị nhân đôi. Đưa mỗi bên về grain "1 đơn" trước thì JOIN là 1-1.</details>
3. Vì sao dùng `customer_key` (surrogate) chứ không dùng thẳng `customer_unique_id` làm khoá?
   <details><summary>Đáp án</summary>(a) JOIN số nguyên nhanh hơn chuỗi 32 ký tự. (b) Độc lập với nguồn: gộp thêm nguồn khác có id khác vẫn chung một khoá. (c) Bắt buộc với SCD2 (phase 3): một người có nhiều phiên bản, mỗi phiên bản một surrogate key riêng.</details>
4. Nếu mai thêm câu hỏi "doanh thu theo **chiến dịch marketing**", cần sửa gì trong mô hình?
   <details><summary>Đáp án</summary>Thêm <code>dim_campaign</code> và cột <code>campaign_key</code> vào fact. Các dim và query cũ không bị ảnh hưởng. Đây là ưu điểm "dễ mở rộng" của star schema.</details>

---
⏭️ **Phase 3**: chuyển cả phase 1 + 2 sang **ELT với dbt**: load thô → transform bằng SQL trong warehouse, kèm test, docs, lineage, SCD2.
