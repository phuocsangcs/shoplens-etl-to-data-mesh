-- Surrogate key = HASH (md5) of the natural key: same product_id -> always the same key, however often we rebuild.
select
    md5(product_id)  as product_key,
    product_id,
    category,
    category_pt,
    photos_qty,
    weight_g,
    volume_cm3,
    case when weight_g < 500   then 'small (<0.5kg)'
         when weight_g < 5000  then 'medium (0.5-5kg)'
         when weight_g is null then 'unknown'
         else 'large (>5kg)' end as weight_class
from {{ ref('stg_products') }}

union all
select '-1', 'unknown', 'unknown', 'unknown', null, null, null, 'unknown'
