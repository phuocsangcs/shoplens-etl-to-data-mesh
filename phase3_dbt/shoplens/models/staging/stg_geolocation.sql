-- 1 triệu dòng -> mỗi zip 1 dòng: toạ độ trung vị, tên thành phố phổ biến nhất (sau chuẩn hoá)
select
    lpad(geolocation_zip_code_prefix, 5, '0')     as zip_code_prefix,
    median(geolocation_lat)                       as lat,
    median(geolocation_lng)                       as lng,
    mode({{ normalize_city('geolocation_city') }}) as city,
    mode(geolocation_state)                       as state
from {{ source('olist', 'geolocation') }}
group by 1
