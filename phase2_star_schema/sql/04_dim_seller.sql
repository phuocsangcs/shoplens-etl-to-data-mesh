-- =====================================================================
-- DIMENSION: dim_seller. GRAIN: mỗi dòng = 1 seller.
-- Gắn sẵn toạ độ (lat/lng) từ bảng geolocation đã làm sạch ở phase 1.
-- =====================================================================
CREATE OR REPLACE TABLE mart.dim_seller AS
SELECT
    ROW_NUMBER() OVER (ORDER BY s.seller_id) AS seller_key,
    s.seller_id,
    s.seller_city            AS city,
    s.seller_state           AS state,
    s.seller_zip_code_prefix AS zip_code_prefix,
    g.lat,
    g.lng
FROM clean.sellers s
LEFT JOIN clean.geolocation g ON g.zip_code_prefix = s.seller_zip_code_prefix

UNION ALL
SELECT -1, 'unknown', 'unknown', 'unknown', '00000', NULL, NULL;
