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

## Airtable base

One Airtable base holds the two tables the pipeline cannot get from an API. You create them by
hand; the pipeline only reads them. Both must exist, even if `transactions` is empty, because
they are fetched together and a missing table fails the whole Airtable step.

Field names are read exactly as written: lowercase, in English (`isin`, not `ISIN`). A field
with any other name is silently ignored. The table names may differ from `instruments` and
`transactions` if you set the `AIRTABLE_INSTRUMENTS_TABLE` and `AIRTABLE_TRANSACTIONS_TABLE`
variables of the `private` GitHub environment (names or `tbl…` IDs).

### `instruments`: what each instrument is

One row per instrument you hold anywhere, **Indexa funds included**, plus the benchmark. Indexa
reports what you own but not how to classify it or where to find its daily price; this table
adds both. An Indexa fund without a row still appears, as "Unclassified" and without an EODHD
price. Rows without an `isin` are ignored.

| Field | Airtable type | Required | Meaning | Example |
|---|---|---|---|---|
| `isin` | Single line text (primary field) | Yes | The instrument's ISIN, the key that links it to its transactions and Indexa positions. Instruments without an ISIN, such as crypto, use a stable made-up ID. | `IE00B4L5Y983` |
| `name` | Single line text | Yes | Display name in the app and the assistant's answers. | `iShares Core MSCI World UCITS ETF` |
| `eodhd_symbol` | Single line text | For a daily price | EODHD ticker with its exchange suffix. The pipeline fetches a daily close for every symbol listed here. Leave it empty only if no price is needed. | `EUNL.XETRA` |
| `asset_class` | Single select | Recommended | What the instrument invests in: `Equity`, `Fixed income`, `Money market`, `Mixed`, `Real estate`, `Commodities`, `Crypto`. Groups the allocation chart. Empty shows as "Unclassified". | `Equity` |
| `region` | Single select | Recommended | Where the instrument's holdings are, not where it is listed: `Global`, `Europe`, `Eurozone`, `North America`, `Emerging markets`, `China`… Groups the allocation by region. Empty shows as "Unclassified". | `Global` |
| `instrument_type` | Single select | Recommended | The wrapper you hold it through, independent of what it holds. Groups the allocation by type. Empty shows as "Unclassified". Values below. | `ETF` |
| `liquidity` | Single select | Recommended | How quickly it can be turned into cash. Groups the allocation by liquidity, to see how much is available at short notice. Empty shows as "Unclassified". Values below. | `Immediate` |
| `currency` | Single line text | No | Currency of the listing you trade, not the fund's base currency (an ETF with "USD" in its name bought on Xetra trades in EUR). Only EUR is supported for now, which is also the default, so it can be left empty. | `EUR` |
| `is_benchmark` | Checkbox | No | Tick on the one instrument you compare the portfolio against. It is priced but never counted as a holding. See [Choosing a benchmark](#choosing-a-benchmark). | ☐ |

`instrument_type` values:

| Value | Meaning | Example |
|---|---|---|
| `ETF` | Exchange-traded fund, bought and sold on an exchange like a share | Amundi Stoxx Europe 600 |
| `ETC` | Exchange-traded commodity, usually backed by a physical commodity | Xetra-Gold |
| `Index fund` | Mutual fund tracking an index, bought and sold through the fund manager | The funds in an Indexa funds account |
| `Pension plan` | Retirement savings plan with withdrawal restrictions | Indexa Más Rentabilidad Acciones PP |
| `Share` | A listed company's shares | SAP |
| `Private shares` | Shares in an unlisted company | A startup |
| `Crypto` | A cryptocurrency held directly | Bitcoin |

`liquidity` values:

| Value | Meaning | Example |
|---|---|---|
| `Immediate` | Sold on an exchange within seconds; cash settles in about 2 working days | ETFs, ETCs, listed shares, crypto |
| `Days` | Sold on request; cash arrives within about a week | Index funds: sold at the next day's price, then transferred |
| `Restricted` | Only withdrawable in specific situations | Spanish pension plans: retirement, long-term unemployment, serious illness, or contributions at least 10 years old |
| `Illiquid` | No market; sold only if a buyer appears | Startup shares: usually only at a funding round, an acquisition or an IPO |

Example rows, an ETF held at a broker and a cryptocurrency:

| isin | name | eodhd_symbol | asset_class | region | instrument_type | liquidity | currency | is_benchmark |
|---|---|---|---|---|---|---|---|---|
| `IE00B4L5Y983` | iShares Core MSCI World UCITS ETF | `EUNL.XETRA` | Equity | Global | ETF | Immediate | EUR | ☐ |
| `CRYPTO-BTC` | Bitcoin | `BTC-EUR.CC` | Crypto | Global | Crypto | Immediate | EUR | ☐ |

### `transactions`: buys and sells outside Indexa

One row per trade at an account the pipeline cannot read through an API: another broker, an
exchange, a crypto wallet. **Do not enter Indexa trades here**; they come from Indexa's API and
would be counted twice. Every `isin` used here needs a row in `instruments`.

| Field | Airtable type | Required | Meaning | Example |
|---|---|---|---|---|
| `date` | Date | Yes | Trade date. Positions and returns change from this day. | `2026-03-02` |
| `isin` | Single line text | Yes | The instrument traded, matching an `isin` in `instruments`. | `IE00B4L5Y983` |
| `type` | Single select | Yes | `buy` or `sell` (case does not matter). Other values are kept but do not change the position. | `buy` |
| `quantity` | Number (decimals) | Yes | Units traded, always positive; `type` gives the direction. | `10` |
| `price` | Number (decimals) | Yes | Price per unit in EUR, before fees. | `98.40` |
| `fees` | Number (decimals) | No | Commission paid on the trade, 0 if empty. Added to the cost of a buy and taken off the proceeds of a sale. | `1.50` |
| `account` | Single line text | Recommended | Where the trade happened, to tell accounts apart. "Manual" if empty. | `Trade Republic` |

Example row, a buy of the ETF above:

| date | isin | type | quantity | price | fees | account |
|---|---|---|---|---|---|---|
| 2026-03-02 | `IE00B4L5Y983` | buy | 10 | 98.40 | 1.50 | Trade Republic |

The pipeline records this buy as €985.50 invested (10 × 98.40 + 1.50). From 2 March on, the
position is 10 units valued at each day's `EUNL.XETRA` close.

### Classifying instruments

The values of `asset_class`, `region`, `instrument_type` and `liquidity` are labels you choose;
the app only groups by them. Use Single select fields so each value is always spelled the same.
The four fields answer different questions:

- `asset_class`: what does it invest in? A stock ETF is `Equity`, a bond ETF `Fixed income`.
  "ETF" is not an asset class; it goes in `instrument_type`.
- `region`: where are the holdings? An Irish-domiciled ETF holding Chinese companies is
  `China`. Euro cash and euro interest-rate funds are `Eurozone`, so they are not counted as
  European equity exposure.
- `instrument_type`: what wrapper do you hold it through?
- `liquidity`: how fast could it become cash?

Worked examples:

| Instrument | asset_class | region | instrument_type | liquidity |
|---|---|---|---|---|
| Amundi Stoxx Europe 600 ETF | Equity | Europe | ETF | Immediate |
| iShares Global Clean Energy ETF | Equity | Global | ETF | Immediate |
| iShares MSCI China Tech ETF | Equity | China | ETF | Immediate |
| Xtrackers EUR Overnight Rate Swap ETF | Money market | Eurozone | ETF | Immediate |
| An equity index fund in an Indexa funds account | Equity | the fund's region | Index fund | Days |
| A bond index fund in an Indexa funds account | Fixed income | the fund's region | Index fund | Days |
| Indexa Más Rentabilidad Acciones PP | Equity | Global | Pension plan | Restricted |
| Indexa Más Rentabilidad Bonos PP | Fixed income | Global | Pension plan | Restricted |
| Shares in a startup | Equity | the company's country | Private shares | Illiquid |

**Indexa.** Add a row for every instrument Indexa holds for you, but never its trades: the
monthly automatic purchases and everything else come from Indexa's API.

- *Funds account*: one row per index fund you own, with its real ISIN (shown on the fund's page
  in Indexa). `eodhd_symbol` is optional: EODHD usually lists such funds as `<ISIN>.EUFUND`;
  check with one call. With a symbol, the fund gets about a year of price history; without one,
  it is priced from Indexa's daily snapshot from the first pipeline run on, and valued at cost
  before that.
- *Pension plan*: you own units of the plans themselves (Acciones and Bonos), not the funds they
  invest in, so add one row per plan. Pension plans have no ISIN; use the plan's DGSFP code
  (from its key information document) or the identifier Indexa's API uses. Leave
  `eodhd_symbol` empty: plans are not listed, and their price comes from Indexa's snapshot.

The dbt test `assert_instruments_are_classified` warns about every held instrument without a
row here and shows the identifier Indexa uses; copy it into `isin`.

**Private shares.** There is no ISIN, so use a stable made-up ID such as `PRIVATE-ACME`, the same
in both tables. Leave `eodhd_symbol` empty. With no market price, the position is valued at what
you paid.

### Choosing a benchmark

A benchmark is a yardstick: an instrument you do not own, used to ask "would I have done better
just buying this?" Tick `is_benchmark` on its row and give it an `eodhd_symbol`. The pipeline
prices it every day but never counts it as a holding. The Portfolio analysis page charts your
return next to the benchmark's, both starting from zero on the first day they share.

Choose one that carries about the same risk as your target allocation, and keep it fixed:
change it only when you deliberately change your strategy. A portfolio of about half stocks and
half bonds and cash compared with a 100% stock index would trail it in good years and beat it in
crashes, both because of risk rather than choices. A single fund with a fixed mix, such as
Vanguard LifeStrategy 40% or 60% Equity, is a fair yardstick that never needs updating.

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
- Ingestion logs row counts only. HTTP errors are reduced to a status code, plus the Airtable
  table name or the Indexa endpoint template, never a URL (the EODHD token travels in it) or an
  account number.
- The app and the assistant use a role that can only `select` from `gold` ([sql/roles.sql](../sql/roles.sql)).
- Tool arguments are validated; the one dynamic column name comes from a whitelist.
- The demo is open to anyone, so the assistant's API spend has four layers of protection:
  an optional access code (`ASSISTANT_ACCESS_CODE`) that strangers don't have; an optional
  cap on questions per day across all visitors (`ASSISTANT_DAILY_LIMIT`), counted per app
  process and so reset when Streamlit restarts the app; a per-session question limit; and
  the Anthropic Console's monthly spend limit on the demo's key, the only hard limit.

### One-time setup

1. **Neon**: create two projects, one private and one for the demo. In each, run the pipeline
   once, then run `sql/roles.sql` with a generated password.
2. **GitHub**: create the environments `private` and `demo`, add their secrets, and restrict
   `private` to the `main` branch (Settings → Environments → Deployment branches). Enable
   secret scanning push protection.
3. **Airtable**: create a base with the `instruments` and `transactions` tables described in
   [Airtable base](#airtable-base). Put its `app…` ID in the `AIRTABLE_BASE_ID` secret.
4. **Tokens**: give each the least access that works: an Airtable personal access token with
   only the `data.records:read` scope on that one base, and a pipeline database role separate
   from the app's.
5. **Google**: create an OAuth client and put it in the private app's `[auth]` secrets
   ([.streamlit/secrets.toml.example](../.streamlit/secrets.toml.example)).
6. **Anthropic**: set a monthly spend limit on the API key used by the demo.

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
