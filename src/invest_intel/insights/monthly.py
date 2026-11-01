"""Monthly insights email.

Usage: `python -m invest_intel.insights.monthly [--month YYYY-MM] [--dry-run PATH]`.

The assistant writes a short, plain-language summary of the past month from the same tools the
app uses, and it is emailed to the owner over SMTP (sent from and to the owner's own address,
with an app password limited to sending).

Runs in a public GitHub Actions log, so it logs only whether the email was sent, never the
summary, the addresses or any figure. It never runs on the demo.
"""

from __future__ import annotations

import argparse
import logging
import smtplib
import sys
from datetime import date, timedelta
from email.message import EmailMessage
from pathlib import Path

import markdown

from invest_intel import config
from invest_intel.assistant import agent

log = logging.getLogger("insights")

PROMPT = """\
Write my monthly portfolio summary for {month_name} ({first} to {last}), to be read as an \
email. Keep it short, in plain language, with these headings:

## The month in brief
How much the portfolio's value changed over the month and how much money I added, from \
get_portfolio_performance (daily, {first} to {last}), and what the investments themselves \
gained or lost that month, from get_monthly_summary.

## Returns
My money-weighted return (MWR) and time-weighted return (TWR), both per year, from \
get_portfolio_summary and get_monthly_summary, and how the month compares with the benchmark, \
from compare_with_benchmark starting {first}.

## My plan
Only the limits that are clearly out of range (ignore the "Slightly" ones), from \
get_investment_plan, with the amount to fix each.

## Worth a look
Two or three short observations that respect my plan's rules.

Every figure must come from the tools. No greeting or sign-off; I know it's from my dashboard."""


def previous_month(today: date) -> tuple[date, date]:
    """First and last day of the month before `today`'s month."""
    last = today.replace(day=1) - timedelta(days=1)
    return last.replace(day=1), last


def month_bounds(value: str) -> tuple[date, date]:
    """First and last day of a YYYY-MM month."""
    first = date.fromisoformat(f"{value}-01")
    next_first = (first + timedelta(days=32)).replace(day=1)
    return first, next_first - timedelta(days=1)


def write_summary(first: date, last: date) -> str:
    prompt = PROMPT.format(
        month_name=first.strftime("%B %Y"), first=first.isoformat(), last=last.isoformat()
    )
    return agent.answer([{"role": "user", "content": prompt}])


def build_email(summary: str, first: date, sender: str, recipient: str) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = f"Portfolio summary – {first.strftime('%B %Y')}"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(summary)
    body = markdown.markdown(summary, extensions=["tables"])
    message.add_alternative(
        f'<html><body style="font-family: sans-serif; max-width: 640px">{body}</body></html>',
        subtype="html",
    )
    return message


def send(message: EmailMessage) -> None:
    host = config.require("SMTP_HOST")
    port = int(config.env("SMTP_PORT", "465"))
    with smtplib.SMTP_SSL(host, port, timeout=30) as smtp:
        smtp.login(config.require("SMTP_USER"), config.require("SMTP_PASSWORD"))
        smtp.send_message(message)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--month", help="YYYY-MM; default: the previous complete month")
    parser.add_argument("--dry-run", type=Path, help="write the email to this .eml file instead")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if config.is_demo():
        log.error("The monthly email never runs on the demo.")
        return 2

    first, last = month_bounds(args.month) if args.month else previous_month(date.today())
    try:
        summary = write_summary(first, last)
        message = build_email(
            summary, first, config.require("MAIL_FROM"), config.require("MAIL_TO")
        )
        if args.dry_run:
            args.dry_run.write_bytes(bytes(message))
            log.info("written to %s", args.dry_run)
        else:
            send(message)
            log.info("sent")
    except Exception as exc:  # noqa: BLE001 - the log is public: the error type only
        log.error("not sent: %s", type(exc).__name__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
