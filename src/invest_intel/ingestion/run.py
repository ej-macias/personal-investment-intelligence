"""Ingestion entry point: `python -m invest_intel.ingestion.run [--source airtable indexa eodhd]`.

Logs contain row counts only. GitHub Actions logs are public on a public repository, so
nothing here may print payloads, account numbers, request URLs or raw exception messages.
"""

from __future__ import annotations

import argparse
import logging
import sys
import uuid

import httpx

from invest_intel import config, db
from invest_intel.ingestion import airtable, bronze, eodhd, indexa

log = logging.getLogger("ingestion")

# Airtable first: EODHD reads the symbols to fetch from the instruments it loads.
SOURCES = ("airtable", "indexa", "eodhd")


def _describe(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code}"
    return type(exc).__name__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", nargs="+", choices=SOURCES, default=list(SOURCES))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if config.is_demo():
        log.error("APP_ENV=demo never calls the source APIs. Use invest_intel.synthetic.generate.")
        return 2

    run_id = uuid.uuid4().hex
    failed: list[str] = []
    with db.connect() as conn:
        bronze.ensure_tables(conn)
        for source in (s for s in SOURCES if s in args.source):
            try:
                if source == "airtable":
                    tables = airtable.fetch()
                elif source == "indexa":
                    tables = indexa.fetch()
                else:
                    tables = eodhd.fetch(conn)
                for table, rows in tables.items():
                    inserted = bronze.load(conn, table, rows, run_id)
                    log.info("%s: %d fetched, %d new or changed", table, len(rows), inserted)
            except Exception as exc:  # noqa: BLE001 - one source failing must not block the rest
                conn.rollback()
                failed.append(source)
                log.error("%s failed: %s", source, _describe(exc))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
