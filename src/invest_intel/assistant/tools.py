"""Tools the AI assistant may call.

The model never sees SQL or a database connection. It can only pick one of these tools and
supply arguments, which are validated here before reaching the fixed queries in
invest_intel.analytics.queries. To give the assistant a new ability, add a query there and
register it below.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from typing import Any

from invest_intel.analytics import queries

# Never sent to the API: for Indexa the account id is the account number. The dashboards still
# show it, since they read the same queries directly.
PRIVATE_FIELDS = frozenset({"account_id"})

_DATE = {"type": "string", "description": "ISO date, YYYY-MM-DD."}
_FREQUENCY = {
    "type": "string",
    "enum": list(queries.FREQUENCIES),
    "description": "Use monthly unless the question needs day-level detail.",
}


def _date(value: Any) -> date | None:
    return date.fromisoformat(value) if value else None


def _get_portfolio_summary(_: dict[str, Any]) -> Any:
    return queries.portfolio_summary()


def _get_portfolio_performance(args: dict[str, Any]) -> Any:
    return queries.portfolio_performance(
        start_date=_date(args.get("start_date")),
        end_date=_date(args.get("end_date")),
        frequency=args.get("frequency", "monthly"),
    )


def _get_asset_allocation(args: dict[str, Any]) -> Any:
    return queries.asset_allocation(args.get("dimension", "asset_class"))


def _get_investment_returns(_: dict[str, Any]) -> Any:
    return queries.investment_returns()


def _compare_with_benchmark(args: dict[str, Any]) -> Any:
    return queries.compare_with_benchmark(
        start_date=_date(args.get("start_date")), frequency=args.get("frequency", "monthly")
    )


def _get_transactions(args: dict[str, Any]) -> Any:
    return queries.transactions(isin=args.get("isin"), limit=args.get("limit", 50))


def _get_monthly_summary(_: dict[str, Any]) -> Any:
    return {
        "annual_return": queries.annual_return(),
        "highlights": queries.highlights(),
        "months": queries.monthly_summary(),
    }


def _get_investment_plan(_: dict[str, Any]) -> Any:
    plan = queries.investment_plan()
    checks = queries.target_checks()
    fees = [r["yearly_fee"] for r in queries.investment_returns() if r.get("yearly_fee")]
    return {
        "plan": plan or None,
        "target_checks": checks,
        "total_yearly_fees": round(sum(fees), 2) if fees else None,
        "note": None
        if plan or checks
        else "No plan or targets in Airtable yet; suggestions can only be general.",
    }


def _tool(name: str, description: str, properties: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": properties or {},
            "additionalProperties": False,
        },
    }


TOOLS: list[dict[str, Any]] = [
    _tool(
        "get_portfolio_summary",
        "Latest total market value, net invested amount, total gain, and the time-weighted "
        "return since the start (cumulative_twr) and per year (twr_per_year). Start here for "
        "any question about how the portfolio stands today.",
    ),
    _tool(
        "get_portfolio_performance",
        "Time series of market value, net invested, total gain and time-weighted return. "
        "Use for questions about performance over a period or how the portfolio evolved.",
        {"start_date": _DATE, "end_date": _DATE, "frequency": _FREQUENCY},
    ),
    _tool(
        "get_asset_allocation",
        "Current market value and portfolio weight grouped by a dimension. "
        "Use for diversification, concentration and exposure questions, and for liquidity: "
        "how much could be turned into cash quickly.",
        {"dimension": {"type": "string", "enum": sorted(queries.ALLOCATION_DIMENSIONS)}},
    ),
    _tool(
        "get_investment_returns",
        "One row per holding with quantity, net invested, market value, gain and return. "
        "Use to find best and worst performers or to look up an instrument's ISIN.",
    ),
    _tool(
        "compare_with_benchmark",
        "Portfolio and benchmark cumulative returns, rebased to zero at start_date, and the "
        "difference between them. Use for questions about beating or lagging the market.",
        {"start_date": _DATE, "frequency": _FREQUENCY},
    ),
    _tool(
        "get_investment_plan",
        "The owner's own plan: goal, horizon year, personal rules, average money added per "
        "month over the last year, and each of their limits (min / target / max share of the "
        "portfolio by asset class, region, type, liquidity, platform or holding) checked "
        "against today: status, and euros to add or reduce to get within range and to reach "
        "the target. Also the total yearly fund fees in EUR. Call this first for any request "
        "for suggestions, rebalancing, where to put new money, risk or costs.",
    ),
    _tool(
        "get_monthly_summary",
        "The money-weighted return per year (annual_return: how the owner's own money grew, "
        "given when it was added; null with under 3 months of history), month-by-month value, "
        "money added, gain "
        "and return, and highlights: best and worst month, share of months with a gain, the "
        "biggest drop from a previous high and how far below its high the portfolio is now. "
        "Use for questions about personal return, good and bad months, and ups and downs.",
    ),
    _tool(
        "get_transactions",
        "Most recent buys and sells, optionally for one instrument.",
        {
            "isin": {
                "type": "string",
                "description": "Instrument ISIN from get_investment_returns.",
            },
            "limit": {"type": "integer", "description": "Maximum rows, default 50."},
        },
    ),
]

HANDLERS: dict[str, Callable[[dict[str, Any]], Any]] = {
    "get_portfolio_summary": _get_portfolio_summary,
    "get_portfolio_performance": _get_portfolio_performance,
    "get_asset_allocation": _get_asset_allocation,
    "get_investment_returns": _get_investment_returns,
    "compare_with_benchmark": _compare_with_benchmark,
    "get_investment_plan": _get_investment_plan,
    "get_monthly_summary": _get_monthly_summary,
    "get_transactions": _get_transactions,
}


def _redact(value: Any) -> Any:
    """Drop PRIVATE_FIELDS from a query result (a row or a list of rows)."""
    if isinstance(value, list):
        return [_redact(v) for v in value]
    if isinstance(value, dict):
        return {k: v for k, v in value.items() if k not in PRIVATE_FIELDS}
    return value


def run_tool(name: str, args: dict[str, Any]) -> tuple[str, bool]:
    """Execute a tool and return (JSON result or error message, is_error)."""
    handler = HANDLERS.get(name)
    if handler is None:
        return f"Unknown tool: {name}", True
    try:
        return json.dumps(_redact(handler(args or {})), default=str), False
    except (ValueError, TypeError) as exc:
        return f"Invalid arguments: {exc}", True
    except Exception as exc:  # noqa: BLE001 - report the failure to the model, not the details
        return f"The tool failed ({type(exc).__name__}).", True
