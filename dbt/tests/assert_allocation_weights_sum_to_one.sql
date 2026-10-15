select sum(weight) as total_weight
from {{ ref('asset_allocation') }}
having abs(sum(weight) - 1) > 0.0001
