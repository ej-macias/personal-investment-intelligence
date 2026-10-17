# Architecture

## Review of the proposed design

The proposal holds up: three sources, PostgreSQL on Neon, medallion layers built by dbt,
GitHub Actions for scheduling, Streamlit with a tool-calling assistant. The skeleton keeps
all of it and changes or adds the following.

| Topic | Decision | Why |
|---|---|---|
| Bronze tables | Store raw payloads as JSONB in append-only tables with one common shape, instead of typed tables such as `indexa_positions` | Ingestion stays trivial and never breaks on a new field; all parsing, typing and deduplication is dbt's job and is tested there |
| Idempotent loads | A record is inserted only if its content hash is new | Daily full refreshes of small endpoints add no rows; the database stays small |
| Positions | Rebuilt from transactions in `fct_positions_daily`; Indexa's own snapshot is used to reconcile | Gives a full daily history rather than only the days the job ran, and yields a real data-quality test |
| Prices | EODHD first, then the price in Indexa's portfolio snapshot, then forward fill | Indexa funds get a daily price without spending EODHD calls |
| EODHD quota | Each run requests only symbols that are behind, stalest first, only the missing dates, capped by `EODHD_DAILY_CALL_BUDGET` | One call per symbol per day at most; a backlog clears over several days instead of failing |
| Instrument metadata | The Airtable `instruments` table maps ISIN to EODHD symbol, asset class and region, and marks the benchmark | One hand-maintained place; holdings are not listed in the public repository |
| Demo isolation | A separate database fed by a generator that writes a fictional portfolio in the same raw payload shapes, valued at real EODHD closes of public ETFs | The whole pipeline is exercised identically on real market moves; Indexa and Airtable are never called, so no personal row can reach the demo |
| Assistant access | Tools call fixed queries through a read-only role limited to `gold` | The model cannot read raw payloads or run arbitrary SQL, even if a prompt asks it to |
| One query layer | Dashboards and assistant tools call the same functions | A number in a chart and the same number in an answer cannot disagree |
| Login | Streamlit's built-in `st.login()` with Google, plus an email allowlist that fails closed | No password handling in the app; works well on a phone |
| CI | Runs the synthetic pipeline and `dbt build` against a PostgreSQL service container | Every change is tested end to end without touching real data |

## Table catalogue

### Bronze: schema `raw`

Columns in every table: `id, run_id, loaded_at, entity, record_key, payload, payload_hash`.

| Table | `entity` | `record_key` |
|---|---|---|
| `indexa_portfolio` | account number | snapshot date |
| `indexa_instrument_transactions` | account number | transaction reference |
| `indexa_cash_transactions` | account number | transaction reference |
| `airtable_instruments` | Airtable table | record id |
| `airtable_transactions` | Airtable table | record id |
| `eodhd_prices` | symbol | price date |

### Silver: schema `silver`

| Model | Grain |
|---|---|
| `stg_indexa__transactions` | transaction |
| `stg_indexa__positions` | account, snapshot date, instrument |
| `stg_airtable__instruments` | instrument |
| `stg_airtable__transactions` | transaction |
| `stg_eodhd__prices` | symbol, date |
| `int_prices_daily` | instrument, calendar day (forward filled) |

### Gold: schema `gold`

| Model | Grain | Answers |
|---|---|---|
| `dim_instrument` | instrument | What is this holding? |
| `fct_transactions` | buy or sell | What did I trade? |
| `fct_positions_daily` | account, instrument, day | What did I hold and what was it worth? |
| `portfolio_performance` | day | Value, net invested, gain, time-weighted return |
| `investment_returns` | account, instrument | Cost, value and gain per holding today |
| `asset_allocation` | instrument | Weights by asset class, region or instrument |
| `benchmark_comparison` | benchmark, day | Am I ahead of or behind the market? |

Candidates for later: `fct_cash_flows` (deposits, withdrawals, fees), `portfolio_performance_monthly`,
`allocation_drift` against target weights, and a money-weighted return per account.

### Method notes

- **Return** is time-weighted: each day's change excludes money added or withdrawn that day.
- **Net invested** is buys minus sale proceeds, so total gain includes realised gains.
- Positions with no price yet are valued at cost and flagged `is_price_estimated`. When the
  first real price arrives, the difference shows up as that day's return.
- Prices use the unadjusted close. Dividends paid in cash are not modelled yet.

## Security

### Where secrets live

No secret is stored in the repository. Each one lives in exactly one of these places:

| Place | Holds | Used by |
|---|---|---|
| `.env` on your machine (git-ignored) | Whatever you need locally | Local runs |
| GitHub environment `private` | Indexa, Airtable and EODHD tokens; pipeline database role | [pipeline.yml](../.github/workflows/pipeline.yml) |
| GitHub environment `demo` | Demo database credentials and the EODHD key (shared with `private`; it reads public prices only, so a leak costs quota, not data) | [demo.yml](../.github/workflows/demo.yml) |
| Streamlit app secrets (private app) | Read-only database role, Anthropic key, Google OAuth client, allowlist | The private app |
| Streamlit app secrets (demo app) | Demo read-only role, Anthropic key | The public demo |

GitHub encrypts environment secrets, never shows them again after saving, masks them in logs
and does not pass them to pull requests from forks. The workflows refer to them by name.

### Safeguards in the code

- `APP_ENV=demo` makes the ingestion refuse to run, and the synthetic generator (which
  truncates the raw tables) refuses to run anywhere else. With `--real-prices` it calls EODHD
  for the demo's public symbols only, and fetches before truncating, so a failed call leaves
  the previous demo data in place.
- Ingestion logs row counts only. HTTP errors are reduced to a status code because the EODHD
  token travels in the URL.
- The app and the assistant use a role that can only `select` from `gold` ([sql/roles.sql](../sql/roles.sql)).
- Tool arguments are validated; the one dynamic column name comes from a whitelist.
- The assistant has a per-session question limit, since the demo is open to anyone.

### One-time setup

1. **Neon**: create two projects, one private and one for the demo. In each, run the pipeline
   once, then run `sql/roles.sql` with a generated password.
2. **GitHub**: create the environments `private` and `demo`, add their secrets, and restrict
   `private` to the `main` branch (Settings → Environments → Deployment branches). Enable
   secret scanning push protection.
3. **Tokens**: give each the least access that works: an Airtable token with read scope on
   the one base, and a pipeline database role separate from the app's.
4. **Google**: create an OAuth client and put it in the private app's `[auth]` secrets
   ([.streamlit/secrets.toml.example](../.streamlit/secrets.toml.example)).
5. **Anthropic**: set a monthly spend limit on the API key used by the demo.

### Things to know

- Questions to the assistant, and the tool results it needs to answer them, are sent to the
  Claude API. Only aggregated `gold` data can be reached this way.
- Scheduled workflows in a public repository are paused by GitHub after 60 days without
  repository activity. [keepalive.yml](../.github/workflows/keepalive.yml) re-enables the
  pipeline and demo workflows monthly to prevent this.

## To verify against the live services

- Indexa endpoint paths and payload field names ([indexa.py](../src/invest_intel/ingestion/indexa.py),
  `stg_indexa__*.sql`), including the values of `operation_type`.
- EODHD free-tier limits and which of your funds it covers; set `EODHD_DAILY_CALL_BUDGET` and
  `EODHD_HISTORY_DAYS` accordingly.
- Current free-tier terms for Neon and Streamlit Community Cloud.
