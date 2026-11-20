-- 1 million rows -> one row per zip: median coordinates, most common city name (after normalization)
select
    lpad(geolocation_zip_code_prefix, 5, '0')     as zip_code_prefix,
    median(geolocation_lat)                       as lat,
    median(geolocation_lng)                       as lng,
    mode({{ normalize_city('geolocation_city') }}) as city,
    mode(geolocation_state)                       as state
from {{ source('olist', 'geolocation') }}
group by 1
