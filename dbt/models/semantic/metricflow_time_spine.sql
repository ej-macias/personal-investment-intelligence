-- One row per day, which MetricFlow uses to roll metrics up to weeks, months and years.
select g.d::date as date_day
from generate_series('2015-01-01'::timestamp, {{ as_of_date() }} + interval '1 year', interval '1 day')
    as g (d)
