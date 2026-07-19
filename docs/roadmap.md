# Roadmap — what we're building

Chosen from the landscape research (2026-07-17). Everything here is wanted;
rejected and already-done items were dropped. Effort: **S** ≈ under an hour,
**M** ≈ a session, **L** ≈ multiple sessions.

Tags: `Feature` new capability · `Upgrade` improves something we have ·
`Principle` a discipline to protect, not a build.

---

## Validation & trust
*Our biggest real gap — the engine is ahead of our ability to trust its output.*

- **Monte Carlo resampling** — `Feature` · S
  Shuffle the trade sequence thousands of times → a distribution of drawdowns
  and risk-of-ruin instead of the one path history happened to give us. We
  already store per-trade R, so this is mostly arithmetic. Cheapest trust win.

- **Walk-forward analysis** — `Upgrade` · M
  Roll the in-sample/out-of-sample split through history: optimise on a window,
  test on the next, stitch the out-of-sample pieces into one curve. The field's
  "gold standard". Our date-range API already supports arbitrary windows.

- **Overfitting guardrails** — `Feature` · M
  Track how many parameter sets we've tried and deflate results accordingly
  (trials counter → Deflated Sharpe / probability-of-overfit). Matters because
  every setting we test makes our best result look better than it is.

- **Parameter optimisation** — `Feature` · M
  Systematic search over strategy params (Optuna). **Build only alongside the
  guardrails above** — an optimiser without overfitting defences reliably
  produces a beautiful, fake strategy. Grid search is the worst offender;
  random search is faster and no worse.

## Data & realism

- **Dukascopy data** — `Feature` · M
  Free real tick/bar forex + **true spot gold** (replaces the GC=F futures
  proxy). Real traded prices instead of Yahoo's indicative quotes. Daily bars
  first so the change is apples-to-apples, intraday later. Keep Yahoo behind a
  `source` field per pair for comparison.
  *Integration points: `get_data()` in `core/data_loader.py` and the ticker in
  `core/pairs.py`. Downloader: `dukascopy-node` (Node is installed). No
  account or payment needed. Expect the numbers to move — that's the point.*

- **Other free sources** — `Feature` · S
  HistData / TrueFX as cross-checks. TrueFX includes real spreads, which is a
  free way to validate the spread estimates in our registry.

- **Better slippage model** — `Upgrade` · S
  Apply slippage to **entries**, not just stop exits (current gap). Fixed-pip
  is fine at our size — market-impact modelling is for players who move price.

## Seeing setups & alerts
*Your stated goal: trade again, and actually see the setups.*

- **TradingView + alerts** — `Feature` · M
  Our strategy as a TradingView indicator that fires alerts on setups. Fastest
  path to trading again — TradingView does the watching. Use
  `once_per_bar_close` to avoid repainting.

- **Phone notifications** — `Feature` · S
  A relay that pushes alerts to your phone (Telegram / ntfy / Pushover). Can
  reuse our existing Flask app as the webhook listener.

- **Job-done notifications** — `Feature` · S
  Push when a **backtest or comparison finishes**, not just on trade setups.
  Rides the same relay as above, so it's nearly free once that exists.

- **Our own watcher** — `Feature` · M
  Our own job pulls data, runs our signal code, and pushes on a setup.
  Guarantees "what I see = what I backtested" by construction, because it's
  the same code — but we own the hosting/uptime.

- **Price chart with trade markers** — `Upgrade` · M
  Candlesticks in our own app with each trade's entry/exit marked. The biggest
  UX gap we have, and the thing that makes setups visible inside the tool.

## Execution & going live
*Plan: **start trading manually**, build the bot in parallel. Broker still TBD
(OANDA is a maybe — it's been acting up), so keep this broker-agnostic.*

- **Broker auto-import to journal** — `Feature` · M
  Pull real fills into the live journal automatically instead of typing them.
  `journal/broker_sync.py` is the placeholder waiting for this. The rule from
  the research: if logging a trade takes over 30 seconds, you'll stop doing it.
  ***Must-not-forget:*** *log the **intended stop distance at entry**. Without
  it a live trade has no R-multiple, and R is the only unit that compares live
  results to the backtest — the broker reports fills, never what your stop was
  meant to be. Also: use the broker's ticket id so a re-synced trade updates
  rather than duplicating, and treat the broker's own profit figure as truth
  (it already includes fees, financing and slippage — that difference from our
  model is exactly what we're trying to measure).*

- **Execution bridge** — `Feature` · M
  Alert → confirm → order placed. The semi-automatic middle ground, and the
  first real step toward the bot.

- **Research-to-live parity** — `Principle` · —
  Live must run the *same* code we backtested, never a re-implementation.
  Already true of the dashboard (it calls the same `run_strategy` as the CLI);
  protect it as the watcher and bot get built.

## Dashboard & UX

- **Compare page** — `Feature` · M
  Saved runs side by side: stats table + overlaid equity curves. `/api/runs` is
  built and tested (keyed by strategy **+ params**, so MA20 and MA50 don't
  overwrite each other) — this only needs the screen.

- **Strategy report page** — `Feature` · M
  Pick one strategy and see everything: every stat and every backtest we've run
  for it, in one place. QuantStats-style depth, per strategy.

- **Click a trade → see it on the chart** — `Upgrade` · S
  Turns the trades table from a log into an investigation tool. Needs the price
  chart first.

- **Interactive charts** — `Upgrade` · S→M
  Hover tooltips first (cheap), zoom/pan later. The field is moving away from
  static charts toward explorable ones.

- **Charting library for candlesticks** — `Feature` · M
  Adopt TradingView Lightweight Charts for price views. A conscious trade
  against our dependency-free stance — recommend using it *only* for
  candlesticks and keeping our hand-drawn SVG for equity curves.

## Trade review
*Raided from the commercial journal apps — this is a mature category worth copying.*

- **Show MAE/MFE** — `Upgrade` · S
  The engine **already records** how far each trade ran for and against us; we
  just never display it. Reveals whether stops are too tight or targets too
  close. Easiest win on this list.

- **Best-exit analysis** — `Feature` · M
  Where we *could* have exited vs where we did — money left on the table.
  Natural extension of MAE/MFE.

- **What-if exit testing** — `Feature` · M
  Replay different exit rules against our *real historical entries*. Separates
  "is my entry good?" from "is my exit good?". Our engine already parameterises
  exits, so this fits unusually well.

- **Tag-based setup analysis** — `Feature` · M
  Tag trades by setup type and see which actually make money versus which just
  feel good. The analytical half of "seeing setups".

- **Trade replay** — `Feature` · M
  Step through a historical trade bar by bar. Sequence after the price chart.

## Analytics

- **More metrics** — `Upgrade` · S
  Profit factor, Sortino, drawdown duration — the field's shared reporting
  language. Profit factor is cheap and high-signal; start there.

- **Performance simulator** — `Feature` · S
  "If my win rate were 45% instead of 40%…" — a small sandbox that builds
  intuition for which lever actually matters.

- **QuantStats tear-sheets** — `Feature` · M
  A library giving 50+ metrics and a full HTML report almost free. Needs a
  trades→returns adapter and adds a dependency; feeds the strategy report page.

---

## Suggested order

By impact ÷ effort, and because trust should come before more surface area:

1. **Show MAE/MFE** — already computed, just surface it
2. **Monte Carlo resampling** — trust, cheap, data in hand
3. **Compare page** — backend done, needs the screen
4. **Phone + job-done notifications** — one relay, two payoffs
5. **Dukascopy** — better data under everything else
6. **Price chart + markers**, then click-through and replay
7. **Walk-forward**, then guardrails + optimisation *(as one piece)*
8. **TradingView indicator**, then watcher, then execution bridge

## Explicitly not doing

Vectorised triage engine (we're not speed-bound: 4 pairs × 10 years ≈ 46 ms) ·
portfolio-construction models (overkill for 4 pairs) · CPCV and synthetic-path
Monte Carlo (research-grade) · AI journaling · no-code strategy builders ·
automated strategy generation · prop-firm sync · OANDA bid/ask feed
*(dropped with the broker decision, revisit if we pick OANDA)*.
