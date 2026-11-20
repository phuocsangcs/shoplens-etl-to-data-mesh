-- Business rule: keep only the LATEST review per order -> order_id becomes a unique key.
-- (In phase 1, changing this rule meant re-extracting. With ELT: edit one line, rerun dbt; raw is still intact.)
select
    review_id,
    order_id,
    review_score,
    trim(regexp_replace(review_comment_title,   '\s+', ' ', 'g')) as review_comment_title,
    trim(regexp_replace(review_comment_message, '\s+', ' ', 'g')) as review_comment_message,
    review_creation_date,
    review_answer_timestamp
from {{ source('olist', 'order_reviews') }}
qualify row_number() over (partition by order_id order by review_answer_timestamp desc) = 1
