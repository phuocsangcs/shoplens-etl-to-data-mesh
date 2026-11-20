select
    md5(s.seller_id) as seller_key,
    s.seller_id,
    s.city,
    s.state,
    s.zip_code_prefix,
    g.lat,
    g.lng
from {{ ref('stg_sellers') }} s
left join {{ ref('stg_geolocation') }} g using (zip_code_prefix)

union all
select '-1', 'unknown', 'unknown', 'unknown', '00000', null, null
