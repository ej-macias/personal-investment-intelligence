# Semantic layer

The metrics are defined once, in [dbt/models/semantic/_semantic.yml](../dbt/models/semantic/_semantic.yml),
on top of the gold models. [MetricFlow](https://docs.getdbt.com/docs/build/about-metricflow)
turns a request such as "portfolio value by month" into SQL, so the same definition is used
however the metric is sliced.

## Metrics

| Metric | Meaning |
|---|---|
| `portfolio_value` | What everything held is worth, on the last day of the period |
| `money_invested` | Money put in minus money taken out, up to the last day of the period |
| `total_gain` | Portfolio value minus money invested |
| `gain_pct` | Total gain as a share of money invested (0.10 means 10%) |
| `money_added` | Money put in minus money taken out during the period |
| `holding_value` | What the holdings are worth; can be split by instrument |
| `holding_money_invested` | Money put into the holdings, net of sales; can be split by instrument |
| `holding_gain` | Holding value minus the money put into it |
| `investment_gain` | What the investments gained or lost, leaving out money added; by month, quarter or year |
| `amount_bought` / `amount_sold` | Money spent on buys / received from sales during the period |

Values on a date (value, money invested, gain) are never added up across days: for a month,
they are the month's last day. Flows (money added, bought, sold) are added up.

They can be grouped by time (`metric_time__day`, `__week`, `__month`, `__quarter`, `__year`)
and, for the holding and trade metrics, by what the instrument is: `instrument__asset_class`,
`instrument__region`, `instrument__instrument_type`, `instrument__liquidity`,
`instrument__instrument_name`.

## Example queries

Run from the `dbt` folder after `make setup` and `make dbt-build` (with `DBT_PROFILES_DIR=.`):

```bash
# Value, money invested and gain at each month end
mf query --metrics portfolio_value,money_invested,total_gain --group-by metric_time__month

# How much was added each month
mf query --metrics money_added --group-by metric_time__month

# Gain % per year
mf query --metrics gain_pct --group-by metric_time__year

# Where the money is today, by asset class
mf query --metrics holding_value,holding_gain --group-by instrument__asset_class \
  --start-time 2026-10-01

# Money spent on buys per quarter, by type
mf query --metrics amount_bought --group-by metric_time__quarter,instrument__instrument_type

# The SQL behind any query
mf query --metrics gain_pct --group-by metric_time__month --explain
```

## Why the app does not use it

The dashboards and the assistant keep their fixed queries in
[queries.py](../src/invest_intel/analytics/queries.py): MetricFlow is too heavy to run inside
Streamlit Community Cloud. The semantic layer is the agreed definition of each metric and the
tool for ad-hoc questions; CI checks that both stay valid (`mf validate-configs`, plus a sample
query on the synthetic data).

The share of each holding in the portfolio is not a metric here: a share of the total depends
on what else is in the grouping, which MetricFlow ratios do not express. It is in the gold
table `asset_allocation`.
