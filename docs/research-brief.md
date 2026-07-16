# Deep-Research Prompt — paste into a chat's research/deep-research mode

*(Saved 2026-07-17. The prompt below is self-contained — it carries its own
project context, so it works pasted into any capable chat assistant.)*

---

You are a quantitative trading research assistant. Produce a detailed,
sourced, prioritized report I can act on. I am a solo retail trader building
my own forex platform and learning as I go. Take your time and be thorough —
I'm running this overnight.

## The project you're advising on

A Python forex strategy-research platform I built:

- **Backtesting engine** — event-driven, bar-by-bar, heavily tested (verified
  against an independent re-implementation and audited for look-ahead bias).
  Supports long & short, per-signal stop-loss / take-profit, trailing and
  break-even stops, limit entries, exit-on-signal, position caps, and costs
  (spread, commission, swap, slippage on stops).
- **Strategies** — drop-in Python files auto-discovered by the app. Currently
  ONE: an MA crossover (buy when Close crosses above its N-bar moving average).
- **Data** — Yahoo Finance (yfinance), daily bars 2015–2024, 4 instruments:
  EUR/USD, GBP/USD, USD/JPY, and gold (XAU/USD — currently the **GC=F futures
  proxy**, not true spot). Yahoo has known quality issues (indicative not
  traded prices; some incoherent bars).
- **Account/risk layer** — fixed-fractional position sizing, leverage, margin
  checks (refuses trades it can't fund).
- **Analysis** — win rate, expectancy in R (risk multiples), max drawdown,
  break-even win rate, exit-reason breakdown.
- **Journal** — SQLite; separate backtest & live tables sharing one schema;
  ready for a broker feed.
- **Front end** — a custom dark web dashboard (Flask + vanilla JS, hand-drawn
  SVG charts, no chart libraries). The Backtest page is complete, including an
  in-sample / out-of-sample date split.
- **I have available**: Python (pandas, Flask, SQLite) and Node.js. I can code.
- **Honest status**: my one strategy's edge is thin-to-negative after costs and
  has only been tested in-sample. I know more features ≠ profit.

## My goal

Start trading again — **manual, or semi-automated (get an alert, confirm, then
place the order)** — and actually **SEE setups, ideally on TradingView via Pine
Script, with a push notification to my phone** when one triggers. Make the whole
thing easier to trade and more trustworthy. I am NOT asking you to invent new
strategies; focus on making the current one visible, tradeable, and trusted.

## Deliverable format (important)

A prioritized report. For EVERY recommendation give:
1. what it is and why it helps *me* specifically,
2. rough effort — Small / Medium / Large,
3. a **FREE option and a PAID option**, each with a one-line note on how it
   affects results/quality/cost (this matters — I want to weigh both).
Cite sources with links so I can verify. Be honest: if something is a
distraction from finding a real edge, say so.

Cover these four areas.

### 1. Seeing & acting on setups  (highest priority)

- Write a faithful **TradingView Pine Script (latest version)** of my MA
  crossover so the chart shows exactly the setups my backtest would take.
  Reproduce this spec precisely:
  - **Long only** for now.
  - **Signal**: Close crosses ABOVE the N-bar simple moving average (N = 20).
  - **Entry**: at the OPEN of the bar AFTER the signal (never same-bar; must
    not repaint).
  - **Exit**: fixed stop-loss and take-profit in **pips** from entry — pip size
    differs by instrument (0.0001 for EUR/GBP, 0.01 for JPY, 0.1 for gold);
    defaults 100-pip stop / 200-pip target on FX, 200 / 400 on gold. Plus a
    **time exit** after N bars (default 10) at that bar's close. Support
    optional trailing stop and break-even.
  - Include `alertcondition()` / alerts that fire on a new setup and on
    stop/target hits.
  - Give me the actual code, commented, ready to paste.
- **Keeping Pine ↔ my Python engine in sync** so "what I see = what I
  backtested": list the specific pitfalls (repainting, next-bar fills, how Pine
  models SL/TP vs a bar-by-bar engine, gaps, pip conversion per pair) and how to
  avoid drift. This faithfulness is the whole point.
- **Phone alerts**: practical routes from a TradingView alert to my phone —
  TradingView mobile push, and webhooks → Telegram bot / Discord / ntfy /
  Pushover. Compare against building my own Python "watcher" that pulls data and
  pushes to my phone. Note TradingView plan limits (number of alerts,
  server-side alerts) in the free-vs-paid split.
- **Semi-automated execution** (alert → I confirm → order placed): broker APIs
  (OANDA and alternatives), TradingView-webhook-to-broker bridges, and a minimal
  self-hosted webhook server. Effort, safety/guardrails, free vs paid.

### 2. Trusting the results before real money  (validation & anti-overfitting)

- Concrete techniques to implement in Python for a **small sample (~100–150
  trades)** retail strategy: walk-forward analysis, out-of-sample testing (I
  already have an IS/OOS date split), parameter-robustness maps, Monte Carlo
  (trade-order shuffle and bootstrap), and appropriate significance tests.
  Which actually matter at this sample size and how to read them.
- How to detect an overfit parameter, and what minimum evidence I should demand
  before trading a strategy live.
- What to add to my dashboard/analysis so "is this trustworthy?" is visible at
  a glance.

### 3. Better data & realistic execution

- **Dukascopy** free historical data (I have Node.js; e.g. dukascopy-node): how
  to pull it, daily first then intraday, and how it compares to Yahoo for my 4
  instruments. Real spot gold vs the GC=F proxy.
- Realistic **spreads, slippage, and swap/financing** for retail FX + gold:
  typical values and how to model them so backtest ≈ live. Free real bid/ask via
  an OANDA practice-account API.
- What moving to **intraday** data changes (e.g. resolving intrabar stop/target
  ambiguity that daily bars can't) and what it costs in complexity.
- Free vs paid data feeds (Dukascopy, OANDA practice, Polygon, Databento, …) —
  what each actually buys me.

### 4. Prioritized roadmap

End with ONE prioritized list of the highest-leverage upgrades across all
areas, ordered by impact ÷ effort toward my goal (trade again, with setups I
can see on TradingView, alerts on my phone, and results I can trust). Tag each
free/paid and S/M/L.

## Ground rules

- Concrete and retail-realistic — no institutional/Bloomberg-tier assumptions.
- Cite sources with links.
- Give me the actual Pine Script, ready to paste.
- Be honest about the thin edge: a trustworthy, tradeable setup beats more
  features every time.
