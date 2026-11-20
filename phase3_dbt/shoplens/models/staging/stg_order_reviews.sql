-- Quy tắc nghiệp vụ: mỗi đơn chỉ giữ review MỚI NHẤT -> order_id thành khoá duy nhất.
-- (Ở phase 1, đổi quy tắc này phải extract lại. Ở ELT: sửa 1 dòng SQL, chạy lại dbt, raw vẫn còn nguyên.)
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
