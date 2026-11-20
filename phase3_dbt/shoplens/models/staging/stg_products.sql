-- ref('...') = tham chiếu model khác. dbt tự suy ra thứ tự chạy (DAG) từ các ref/source này,
-- không cần đánh số 01_, 02_ như phase 2 nữa.
select
    p.product_id,
    coalesce(p.product_category_name, 'unknown')          as category_pt,
    coalesce(t.product_category_name_english, 'unknown')  as category,
    p.product_name_lenght                                 as name_length,         -- sửa lỗi chính tả nguồn
    p.product_description_lenght                          as description_length,
    p.product_photos_qty                                  as photos_qty,
    p.product_weight_g                                    as weight_g,
    p.product_length_cm * p.product_height_cm * p.product_width_cm as volume_cm3
from {{ source('olist', 'products') }} p
left join {{ ref('stg_category_translation') }} t using (product_category_name)
