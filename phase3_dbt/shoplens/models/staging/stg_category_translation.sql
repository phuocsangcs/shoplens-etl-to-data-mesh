-- Original translation table + 2 extra translations from a seed (human-maintained CSV)
select product_category_name, product_category_name_english
from {{ source('olist', 'product_category_name_translation') }}

union all

select product_category_name, product_category_name_english
from {{ ref('category_translation_fixes') }}
