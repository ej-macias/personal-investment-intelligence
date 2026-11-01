# Case study: one place for all my investments

## The problem

Over the last few years I have invested in different kinds of assets: index funds, ETFs, a
pension plan, shares in a startup, and soon crypto, spread across several platforms. Each
platform has its own app or website, so answering simple questions meant checking several of
them on my phone: what do I own, where is it, how is it doing, and what should I do next? None
of them could show a chart that combined everything.

I wanted one place where I could check all of it quickly, see it visually, and ask questions
in plain language.

## Who it is for

The app is for me, to keep track of my own investments. It also has a public demo, so that
anyone interested can try it, and the code is free to use on GitHub. API keys, passwords and,
above all, my financial data are never stored in the repository.

- **Private app:** my real accounts, behind a login that only lets me in.
- **Demo app:** [invest-intel-demo.streamlit.app](https://invest-intel-demo.streamlit.app), a
  fictional portfolio valued at real market prices.

## How it works

Every day a scheduled job collects data from three sources:

- **Indexa Capital's API**: my index funds and pension plan, including the automatic monthly
  contributions, so those never need entering by hand.
- **Airtable**: one of the platforms I invest through has no API, so I record those
  investments by hand. I was already keeping a manual tracking sheet in Airtable, so it became
  the source for them, and for how every instrument is classified. When I make a new
  investment there, I add it myself. That's fine: I invest for the long term, so it doesn't
  happen often.
- **EODHD's API**: daily market prices. The investments I record by hand only say what I
  bought and when, so I need real prices to know what they are worth today.

dbt turns that raw data into clean, tested tables, and a Streamlit app shows dashboards and an
AI assistant on top of them. The details are in [architecture.md](architecture.md).

## Decisions I made

**A demo with a fictional portfolio but real prices.** I wanted the demo to use real data as
much as possible without revealing anything about my finances: not the amounts, and not even
which products I own. The demo's holdings and trades are made up, but they are valued at real
daily prices from EODHD for public ETFs I don't hold. That let me deliver a working MVP fast,
covering every part of the system, including a real API, while keeping my own data completely
separate: the demo has its own database and its own credentials.

**A mixed benchmark instead of a world stock index.** A benchmark only tells you something if
it takes about the same risk as your portfolio. Mine, like most people's, mixes stocks with
bonds and cash. Next to a 100% stock index it would trail far behind in good years and look
great in a crash, because of how much risk I chose to take rather than because my choices
were good or bad. A fixed stock/bond mix that matches my target is a fair yardstick, and since
it's fixed, I don't have to update it whenever my weights move. The demo follows the same
rule: its benchmark is a fund with a fixed 80% stocks and 20% bonds, close to the demo
portfolio's own mix.

**Looking at my money by platform, type and liquidity, not only by asset class.** Knowing how
much I have in stocks or bonds isn't enough. I also want to see how much sits on each
platform, so I don't keep too much of my money in one place; what each investment is (an ETF,
an index fund, a pension plan, private shares); and how quickly I could turn it into cash if I
needed money urgently. Some of it can be sold within days; my pension plan and startup shares
can't.

**Free price data, one day late.** I'm not trading; I'm following mostly long-term
investments. A price that is one day old doesn't change any decision I make, so I chose to
stay within EODHD's free tier instead of paying for more frequent data. When I hold more
instruments than the free quota covers, the pipeline refreshes the oldest prices first and
the rest catch up a day later.

**An assistant with a fixed menu of questions it can answer.** I didn't let the AI assistant write its own database queries. Instead it
chooses from a small set of tested queries, the same ones the dashboards use, and explains the
result. That way every number it quotes comes from a calculation I trust, it can only read the
summary tables, and it can't change anything. When a question falls outside what those tools
cover, it says so instead of guessing.

## What was harder than expected

- **Staying within the free API quotas.** Every source has limits, so the pipeline had to
  plan its calls and carry on when one source fails.
- **Making the app easy to show but safe.** The demo is open to anyone, the private app isn't,
  and nothing personal can leak through logs, screenshots or the public repository. The AI
  assistant in the demo needs an access code and has a daily limit, so strangers can't run up
  costs.

## What I learnt

I built this with Claude Code, which made me much more efficient, caught corner cases I would
have missed, and taught me practical techniques along the way: keeping secrets in GitHub
environments and Streamlit secrets, separating demo and real data completely, and keeping API
costs low.

## What's next

- **Crypto**, probably through the Kraken or Coinbase API.
- **A monthly summary by email**, written by the assistant from the month's data.
- **Documented, visual dbt lineage**, to find gaps and improve the quality and performance of
  the data models.
