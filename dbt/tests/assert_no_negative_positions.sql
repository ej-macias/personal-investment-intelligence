-- Selling more than was ever bought means a transaction is missing or mistyped.
select account_id, isin, date_day, quantity
from {{ ref('fct_positions_daily') }}
where quantity < -0.0001
