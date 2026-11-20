-- ref('...') = reference another model. dbt infers the run order (DAG) from these ref/source calls,
-- no more numbering files 01_, 02_ like in phase 2.
select
    p.product_id,
    coalesce(p.product_category_name, 'unknown')          as category_pt,
    coalesce(t.product_category_name_english, 'unknown')  as category,
    p.product_name_lenght                                 as name_length,         -- fix source typo
    p.product_description_lenght                          as description_length,
    p.product_photos_qty                                  as photos_qty,
    p.product_weight_g                                    as weight_g,
    p.product_length_cm * p.product_height_cm * p.product_width_cm as volume_cm3
from {{ source('olist', 'products') }} p
left join {{ ref('stg_category_translation') }} t using (product_category_name)
