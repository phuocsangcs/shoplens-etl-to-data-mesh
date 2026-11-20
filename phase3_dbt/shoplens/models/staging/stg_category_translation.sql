-- Bảng dịch gốc + 2 bản dịch bổ sung từ seed (CSV do con người duy trì)
select product_category_name, product_category_name_english
from {{ source('olist', 'product_category_name_translation') }}

union all

select product_category_name, product_category_name_english
from {{ ref('category_translation_fixes') }}
