-- =====================================================================
-- SO SÁNH: cùng dữ liệu product nhưng theo kiểu SNOWFLAKE SCHEMA
-- (kiểu mô hình hoá, KHÔNG liên quan tới sản phẩm Snowflake)
--
-- Star:      fact ── dim_product (có sẵn category)
-- Snowflake: fact ── dim_product ── dim_category      (dimension bị chuẩn hoá thêm 1 tầng)
--
-- Ưu: không lặp tên category trên 32k dòng sản phẩm, đổi tên category chỉ sửa 1 chỗ.
-- Nhược: thêm JOIN cho MỌI query. Ngày nay lưu trữ rẻ + column-store nén rất tốt chuỗi lặp
--        -> ngành chủ yếu dùng STAR.
-- =====================================================================
CREATE SCHEMA IF NOT EXISTS mart_snowflake;

CREATE OR REPLACE TABLE mart_snowflake.dim_category AS
SELECT ROW_NUMBER() OVER (ORDER BY category) AS category_key, category, category_pt
FROM (SELECT DISTINCT category, category_pt FROM mart.dim_product);

CREATE OR REPLACE TABLE mart_snowflake.dim_product AS
SELECT p.product_key, p.product_id, c.category_key, p.photos_qty, p.weight_g, p.volume_cm3, p.weight_class
FROM mart.dim_product p
JOIN mart_snowflake.dim_category c USING (category, category_pt);
