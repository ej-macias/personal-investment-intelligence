# Personal Investment Intelligence

A personal investment analytics app. It consolidates investments held at Indexa Capital and
elsewhere, models portfolio performance with dbt, and answers questions in plain language
through an AI assistant that works from a fixed set of analytical tools.

The public demo runs on a fictional portfolio valued at real market prices. The real portfolio lives in a separate, private
database behind a login.

## Architecture

```
 Indexa Capital ─┐
 Airtable ───────┼─▶ Python ingestion ─▶ raw (bronze) ─▶ dbt ─▶ silver ─▶ gold ─▶ Streamlit
 EODHD prices ───┘   GitHub Actions       JSONB,          staging,          marts    ├─ dashboards
                     daily                append-only     typed, tested              └─ AI assistant
                                                                                        (tool calling)
 Synthetic generator ─▶ raw (demo database only)
```

| Layer | Technology | Where |
|---|---|---|
| Ingestion | Python, httpx, psycopg | [src/invest_intel/ingestion/](src/invest_intel/ingestion/) |
| Storage | PostgreSQL (Neon) | schemas `raw`, `silver`, `gold` |
| Transformation and data quality | dbt Core | [dbt/](dbt/) |
| Query layer | Fixed, parameterised SQL over `gold` | [src/invest_intel/analytics/queries.py](src/invest_intel/analytics/queries.py) |
| AI assistant | Claude with tool calling | [src/invest_intel/assistant/](src/invest_intel/assistant/) |
| Front end | Streamlit, Google login | [app/](app/) |
| Scheduling and CI | GitHub Actions | [.github/workflows/](.github/workflows/) |
| Demo data | Synthetic generator | [src/invest_intel/synthetic/generate.py](src/invest_intel/synthetic/generate.py) |

The design decisions, the table catalogue and the security model are in
[docs/architecture.md](docs/architecture.md).

## Data model

- **Bronze (`raw`)**: one append-only table per API endpoint, each storing the source payload
  as JSONB. A record is stored again only when its content changes.
- **Silver**: `stg_*` views that type and deduplicate each source, plus `int_prices_daily`,
  one price per instrument per calendar day.
- **Gold**: `dim_instrument`, `fct_transactions`, `fct_positions_daily`, and the analytical
  tables `portfolio_performance`, `investment_returns`, `asset_allocation` and
  `benchmark_comparison`.

## The AI assistant

The model has no database access and never writes SQL. It chooses among six tools
(`get_portfolio_summary`, `get_portfolio_performance`, `get_asset_allocation`,
`get_investment_returns`, `compare_with_benchmark`, `get_transactions`), each backed by the
same fixed queries the dashboards use, through a database role that can only read `gold`.

## Run the demo locally

Requires Python 3.11+ and a PostgreSQL database (Docker, or a free Neon project).

```bash
cp .env.example .env          # set APP_ENV=demo and the PG* variables
make setup && source .venv/bin/activate
make db-up                    # local PostgreSQL via Docker; skip when using Neon
make demo-data                # synthetic instruments, prices and transactions into raw
make dbt-build                # build and test silver and gold
make app                      # http://localhost:8501
```

The assistant page also needs `ANTHROPIC_API_KEY`. `make test` and `make lint` run the unit
tests and the linter.

## Environments

| | Data | Database | App access |
|---|---|---|---|
| `demo` | Fictional portfolio at real EODHD prices; Indexa and Airtable are never called | Its own Neon project | Open |
| `prod` | Real accounts, via the daily pipeline | Private Neon project | Google login, email allowlist |
| `dev` | Either | Local PostgreSQL | Google login, or use `demo` |

The two deployments share code and nothing else: different databases, different credentials,
different GitHub environments.

## Status

This is the project skeleton. The pipeline, models, dashboards and assistant tools run end to
end on synthetic data. Still to do:

- [ ] Confirm the Indexa payload fields against a live account (`stg_indexa__*.sql`)
- [ ] Create the Airtable base ([fields](docs/architecture.md#airtable-base)), Neon projects, GitHub environments and Streamlit deployments
- [ ] Model cash transactions (deposits, fees) and money-weighted return
- [ ] Multi-currency support (everything is assumed to be EUR)
- [ ] Evaluation set for the assistant's answers
