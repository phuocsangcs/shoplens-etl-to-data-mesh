select
    order_id,
    order_item_id,
    product_id,
    seller_id,
    shipping_limit_date,
    price::double          as price,
    freight_value::double  as freight_value
from {{ source('olist', 'order_items') }}
where price > 0
