select
    order_id,
    payment_sequential,
    payment_type,
    payment_installments,
    payment_value::double as payment_value
from {{ source('olist', 'order_payments') }}
where payment_type <> 'not_defined'
