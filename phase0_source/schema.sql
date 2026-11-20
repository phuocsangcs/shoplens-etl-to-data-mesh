-- =====================================================================
-- Schema DB production (OLTP) của sàn Olist, dựng lại từ 9 file CSV Kaggle.
-- Giữ NGUYÊN tên cột gốc (kể cả lỗi chính tả "lenght") vì nguồn thật là vậy:
-- data engineer không được sửa nguồn, chỉ xử lý ở các bước sau.
--
-- Chuẩn hoá 3NF: mỗi thực thể một bảng, nối bằng khoá ngoại.
--
--   customers 1──n orders 1──n order_items n──1 products ──(category)── category_translation
--                   │                    └──n──1 sellers
--                   ├──n order_payments
--                   └──n order_reviews
--   geolocation: tra cứu toạ độ theo zip code (nhiều dòng / 1 zip)
-- =====================================================================

DROP TABLE IF EXISTS order_reviews, order_payments, order_items, orders,
                     products, sellers, customers, geolocation,
                     product_category_name_translation CASCADE;

CREATE TABLE customers (
    customer_id              TEXT PRIMARY KEY,   -- ⚠️ id THEO ĐƠN: mỗi đơn sinh 1 customer_id mới
    customer_unique_id       TEXT NOT NULL,      -- id thật của một NGƯỜI
    customer_zip_code_prefix TEXT NOT NULL,      -- TEXT vì có số 0 đứng đầu ("01037")
    customer_city            TEXT NOT NULL,
    customer_state           TEXT NOT NULL
);

CREATE TABLE sellers (
    seller_id              TEXT PRIMARY KEY,
    seller_zip_code_prefix TEXT NOT NULL,
    seller_city            TEXT NOT NULL,
    seller_state           TEXT NOT NULL
);

CREATE TABLE product_category_name_translation (
    product_category_name         TEXT PRIMARY KEY,  -- tiếng Bồ Đào Nha
    product_category_name_english TEXT NOT NULL
);

CREATE TABLE products (
    product_id                 TEXT PRIMARY KEY,
    product_category_name      TEXT,             -- có thể NULL
    product_name_lenght        INT,              -- (sic) lỗi chính tả có sẵn trong nguồn
    product_description_lenght INT,
    product_photos_qty         INT,
    product_weight_g           INT,
    product_length_cm          INT,
    product_height_cm          INT,
    product_width_cm           INT
    -- Cố ý KHÔNG có FK tới bảng translation: có category không có bản dịch (xem analytics_pain.sql)
);

CREATE TABLE orders (
    order_id                      TEXT PRIMARY KEY,
    customer_id                   TEXT NOT NULL REFERENCES customers(customer_id),
    order_status                  TEXT NOT NULL,
    order_purchase_timestamp      TIMESTAMP NOT NULL,
    order_approved_at             TIMESTAMP,
    order_delivered_carrier_date  TIMESTAMP,     -- giao cho đơn vị vận chuyển
    order_delivered_customer_date TIMESTAMP,     -- khách nhận hàng
    order_estimated_delivery_date TIMESTAMP NOT NULL
);

-- Grain: mỗi dòng = 1 MÓN hàng trong đơn (mua 2 cái giống nhau = 2 dòng)
CREATE TABLE order_items (
    order_id            TEXT NOT NULL REFERENCES orders(order_id),
    order_item_id       INT  NOT NULL,           -- số thứ tự món trong đơn: 1, 2, 3...
    product_id          TEXT NOT NULL REFERENCES products(product_id),
    seller_id           TEXT NOT NULL REFERENCES sellers(seller_id),
    shipping_limit_date TIMESTAMP NOT NULL,
    price               NUMERIC(10, 2) NOT NULL, -- BRL (real Brazil)
    freight_value       NUMERIC(10, 2) NOT NULL, -- phí ship
    PRIMARY KEY (order_id, order_item_id)
);

-- Grain: mỗi dòng = 1 LẦN thanh toán (1 đơn có thể trả bằng nhiều cách/voucher)
CREATE TABLE order_payments (
    order_id             TEXT NOT NULL REFERENCES orders(order_id),
    payment_sequential   INT  NOT NULL,
    payment_type         TEXT NOT NULL,          -- credit_card, boleto, voucher, debit_card
    payment_installments INT  NOT NULL,          -- trả góp mấy kỳ
    payment_value        NUMERIC(10, 2) NOT NULL,
    PRIMARY KEY (order_id, payment_sequential)
);

CREATE TABLE order_reviews (
    review_id               TEXT NOT NULL,       -- ⚠️ KHÔNG unique trong data thật!
    order_id                TEXT NOT NULL REFERENCES orders(order_id),
    review_score            INT  NOT NULL,       -- 1..5 sao
    review_comment_title    TEXT,
    review_comment_message  TEXT,                -- có xuống dòng bên trong
    review_creation_date    TIMESTAMP NOT NULL,
    review_answer_timestamp TIMESTAMP NOT NULL
);

CREATE TABLE geolocation (
    geolocation_zip_code_prefix TEXT NOT NULL,
    geolocation_lat             DOUBLE PRECISION NOT NULL,
    geolocation_lng             DOUBLE PRECISION NOT NULL,
    geolocation_city            TEXT NOT NULL,   -- ⚠️ cùng 1 thành phố, nhiều cách viết
    geolocation_state           TEXT NOT NULL
);

-- Index phục vụ APP (tra cứu theo khoá), không phải phục vụ phân tích
CREATE INDEX ON orders (customer_id);
CREATE INDEX ON order_items (product_id);
CREATE INDEX ON order_reviews (order_id);
