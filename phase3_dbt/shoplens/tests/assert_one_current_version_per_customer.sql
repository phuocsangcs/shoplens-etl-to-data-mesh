-- SCD2 phải đảm bảo: mỗi người có ĐÚNG 1 phiên bản đang hiệu lực (is_current).
select customer_unique_id, count(*) as current_versions
from {{ ref('dim_customer') }}
where is_current
group by 1
having count(*) <> 1
