-include .env
export

DBT = cd dbt && DBT_PROFILES_DIR=. dbt

.PHONY: setup db-up ingest demo-data dbt-build dbt-docs app test lint

setup:
	python -m venv .venv
	.venv/bin/pip install -e ".[dbt,semantic,insights,dev]"

db-up:
	docker compose up -d

ingest:            ## Pull Airtable, Indexa and EODHD into the raw schema
	python -m invest_intel.ingestion.run

demo-data:         ## Fill the raw schema with synthetic data (requires APP_ENV=demo)
	python -m invest_intel.synthetic.generate

dbt-build:         ## Build and test the silver and gold layers
	$(DBT) build

dbt-docs:
	$(DBT) docs generate && $(DBT) docs serve

app:
	streamlit run app/streamlit_app.py

test:
	pytest

lint:
	ruff check . && ruff format --check .
