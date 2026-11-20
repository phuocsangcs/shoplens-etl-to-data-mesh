-- =====================================================================
-- DIMENSION: dim_date. Mỗi dòng = 1 ngày.
-- Vì sao cần bảng ngày riêng, khi đã có cột timestamp?
--   -> Gom sẵn mọi "cách nhìn" về thời gian (năm, quý, thứ, cuối tuần, Black Friday...)
--      để analyst chỉ cần GROUP BY cột có sẵn, không phải tự viết hàm ngày tháng.
-- Khoá: date_key dạng số YYYYMMDD (20171124): dễ đọc, JOIN nhanh.
-- =====================================================================
CREATE OR REPLACE TABLE mart.dim_date AS
SELECT
    CAST(strftime(d, '%Y%m%d') AS INTEGER)       AS date_key,
    d::DATE                                      AS full_date,
    year(d)                                      AS year,
    quarter(d)                                   AS quarter,
    month(d)                                     AS month,
    strftime(d, '%Y-%m')                         AS year_month,
    monthname(d)                                 AS month_name,
    isodow(d)                                    AS day_of_week,     -- 1 = thứ Hai
    dayname(d)                                   AS day_name,
    isodow(d) IN (6, 7)                          AS is_weekend,
    d::DATE IN ('2016-11-25', '2017-11-24', '2018-11-23') AS is_black_friday
FROM range(TIMESTAMP '2016-01-01', TIMESTAMP '2019-01-01', INTERVAL 1 DAY) AS t(d);
