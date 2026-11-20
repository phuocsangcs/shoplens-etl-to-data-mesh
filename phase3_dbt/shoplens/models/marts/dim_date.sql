select
    cast(strftime(d, '%Y%m%d') as integer)    as date_key,
    d::date                                   as full_date,
    year(d)                                   as year,
    quarter(d)                                as quarter,
    month(d)                                  as month,
    strftime(d, '%Y-%m')                      as year_month,
    monthname(d)                              as month_name,
    isodow(d)                                 as day_of_week,
    dayname(d)                                as day_name,
    isodow(d) in (6, 7)                       as is_weekend,
    d::date in ('2016-11-25', '2017-11-24', '2018-11-23') as is_black_friday
from range(timestamp '2016-01-01', timestamp '2019-01-01', interval 1 day) as t(d)
