# Notes

## 2026-07-15 — Live trade tracker (the "Tracker" page)

Once real money is trading: pull our actual filled trades from the broker's
API and show them with **the same analytics the backtest produces** — win
rate, expectancy in R, max drawdown, exit reasons, equity curve. The point
is a like-for-like comparison: does live match what the backtest promised?
That's the loop that catches broken assumptions before they get expensive
(slippage worse than modelled, spreads wider than the registry's estimate,
signals that fire differently in real time).

Design notes:
- The nav's **Tracker** page is this. `core/journal.py` (manual entries with
  your reasoning) becomes one input; the broker API becomes the other. A
  trade's *reasoning* still has to be typed by a human — the API only knows
  prices and times.
- To reuse `summarize()` and the dashboard's charts unchanged, live trades
  must land in the same shape as the engine's output: entry/exit date+price,
  exit_reason, profit, r_multiple, direction. `r_multiple` needs the stop
  distance we intended, so log it at entry time — the broker won't tell us.
- Broker undecided. OANDA is the obvious candidate (good REST API, free
  practice account, and we may use their data for bid/ask anyway — see the
  data note below), but not committed. Discuss brokers before building.
- Naturally pairs with the data upgrade below: same account, same API.

## 2026-07-15 — Data upgrade: Dukascopy (Swiss bank, free)

When we outgrow Yahoo, the upgrade path is (in order):

1. **Dukascopy** — Swiss bank, gives away **tick-level FX and spot gold (XAU/USD) history for free**, going back ~20 years. Biggest data-quality jump available at $0: real traded prices instead of Yahoo's indicative quotes (which have 30–82 incoherent bars per pair), true spot gold instead of the GC=F futures proxy, and intraday resolution that eliminates the engine's same-bar stop/target ambiguity instead of just flagging it. Needs a downloader tool (e.g. dukascopy-node) — integration point is `get_data()` in core/data_loader.py + the ticker in core/pairs.py.
2. **OANDA practice account (free)** — API candles with real bid/ask for exactly our four pairs → measured spreads instead of the estimated `spread_pips` in the registry.
3. **Paid, only when going live / systematically intraday** — Polygon.io (~$30–200/mo) or Databento (pay-as-you-go, gold futures ticks).

Engine note: it's already bar-size agnostic — feed it hourly bars and every
"day" parameter simply means "bar." No engine changes needed for intraday.
