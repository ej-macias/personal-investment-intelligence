"""Money-weighted return (MWR): the yearly rate that turns the money you put in, when you put
it in, into what you have today.

Brokers show it as "personal return" or "money-weighted return"; spreadsheets call the same
calculation XIRR. Unlike the time-weighted return, it depends on when money was added, so it
answers "how have my own euros done" rather than "how have my investments done".
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

Flow = tuple[date, float]

# Lowest and highest yearly rates searched: -99.99% and +10,000%.
_LOW, _HIGH = -0.9999, 100.0


def _value_today(flows: Sequence[Flow], rate: float) -> float:
    """Every flow carried to the first date at `rate`; zero at the annual return."""
    start = flows[0][0]
    return sum(amount / (1 + rate) ** ((day - start).days / 365) for day, amount in flows)


def per_year(total_return: float, days: int) -> float:
    """A return over `days` days as a yearly rate: 21% over two years is 10% per year."""
    return (1 + total_return) ** (365 / days) - 1


def annual_return(flows: Sequence[Flow]) -> float:
    """Yearly rate for dated flows: money put in negative, money taken out and today's value
    positive. Solved by halving the search interval, which always converges."""
    flows = sorted(flows)
    if not any(a < 0 for _, a in flows) or not any(a > 0 for _, a in flows):
        raise ValueError("Needs money put in (negative) and money out or a value (positive).")

    low, high = _LOW, _HIGH
    f_low = _value_today(flows, low)
    if f_low * _value_today(flows, high) > 0:
        raise ValueError("No annual return between -99.99% and +10,000% fits these flows.")
    for _ in range(200):
        mid = (low + high) / 2
        f_mid = _value_today(flows, mid)
        if f_mid == 0 or high - low < 1e-12:
            break
        if f_low * f_mid < 0:
            high = mid
        else:
            low, f_low = mid, f_mid
    return (low + high) / 2
