-- =====================================================================
-- DIMENSION: dim_product. GRAIN: mỗi dòng = 1 sản phẩm.
-- PHI CHUẨN HOÁ có chủ đích: tên category (cả tiếng Bồ và tiếng Anh) nằm NGAY trong bảng này,
-- thay vì tách sang bảng category riêng như 3NF. -> analyst bớt 1 JOIN.
-- (So sánh với kiểu "snowflake schema" ở file 08.)
-- =====================================================================
CREATE OR REPLACE TABLE mart.dim_product AS
SELECT
    ROW_NUMBER() OVER (ORDER BY product_id)                       AS product_key,
    product_id,
    product_category_name_english                                 AS category,
    product_category_name                                         AS category_pt,
    product_photos_qty                                            AS photos_qty,
    product_weight_g                                              AS weight_g,
    product_length_cm * product_height_cm * product_width_cm      AS volume_cm3,
    CASE WHEN product_weight_g < 500   THEN 'small (<0.5kg)'
         WHEN product_weight_g < 5000  THEN 'medium (0.5-5kg)'
         WHEN product_weight_g IS NULL THEN 'unknown'
         ELSE 'large (>5kg)' END                                  AS weight_class
FROM clean.products

UNION ALL
SELECT -1, 'unknown', 'unknown', 'unknown', NULL, NULL, NULL, 'unknown';
