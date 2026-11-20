-- Where each order ships FROM: the seller of the first item (order_item_id = 1).
select
    i.order_id,
    upper(trim(s.seller_state)) as seller_state
from {{ source('raw', 'order_items') }} i
join {{ source('raw', 'sellers') }} s using (seller_id)
where i.order_item_id = 1
