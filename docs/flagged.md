# Flagged

Things that need **your decision**, or that you should know before trusting a
number or spending money. Not a bug list (that's the GitHub issues). Not
design notes (that's `docs/notes.md`).

Last updated: 2026-07-16

---

## 1. Decisions waiting on you

| # | Decision | My recommendation |
|---|----------|-------------------|
| 1 | **Dukascopy switch: daily or intraday first?** | **Daily first.** Changing the data source *and* the timeframe at once means you can't tell which caused the change in results. |
| 2 | **Keep Yahoo after the switch?** | Yes — add a `source` field to the pair registry rather than ripping yfinance out. Costs nothing, lets us compare sources. |
| 3 | **Broker for the Tracker page.** Undecided. | OANDA is the front-runner (good REST API, free practice account, and we may want their bid/ask data anyway). Not committed — worth a conversation. |
| 4 | **A second strategy — which one?** The discovery system + engine support shorts/limits/trailing, but no strategy uses them. | Your call (it's trading logic). RSI reversal or a breakout would exercise per-signal columns and give the Compare tab a reason to exist. |

---

## 2. Warnings — the ones that could cost real money

### ⚠️ Every result you've seen is in-sample
The parameters (MA 20, 100/200 pip stop/target, 10-day hold) were never
validated on data they weren't chosen against. **This is the single biggest
gap between "interesting" and "believable".** The dashboard can now *do* the
split — the Backtest page has In-sample / Out-of-sample presets — so it's a
two-click check: tune on 2015–2020, then run 2021–2024 **once**. If the edge
survives, it's real. Also check parameter neighbours (MA 15/25, SL 80/120) —
a real edge degrades gently, a fluke collapses.

### ⚠️ Sample size is small enough to fool you
127 trades per pair carries roughly **±8 percentage points** of pure noise on
the win rate. A tweak that "improves" win rate by a few points is
indistinguishable from luck. Any subgroup claim ("stop-outs in 2019") means
essentially nothing.

### ⚠️ The current edge is thin-to-negative on this data
Latest full 4-pair run: **39.6% win rate against a 39.7% break-even** — a
tenth of a point *below* water, expectancy **−0.001R**. Individually, GBPUSD
and gold showed a small positive edge; EURUSD and USDJPY didn't. This is after
spread but **before** swap/financing costs.

### ⚠️ Break-even is ~40%, not the 33% the 1:2 ratio implies
Because time exits cut winners short: realised average win is **+1.45R**, not
+2R. Any intuition built on "1:2 means I only need 33%" is wrong here.

### ⚠️ Daily bars cannot resolve what happened inside a bar
When one bar contains both your stop and your target, the true order is
unknowable. The engine always assumes the stop (pessimistic) and flags the
trade `ambiguous` — currently ~1 trade per pair, so results are essentially
assumption-free today. Only intraday data eliminates it.

### ⚠️ Yahoo data is the known ceiling
30–82 **incoherent bars per pair** (Open/Close outside the High–Low range —
the engine's envelope rule defends against exactly this), indicative rather
than traded quotes, and **gold is the GC=F futures proxy, not spot**.

---

## 3. Data source status: still Yahoo, nothing switched

Re-checked 2026-07-16 — **no part of the Dukascopy plan is implemented**:
`core/pairs.py` tickers are Yahoo symbols (`EURUSD=X`, `GC=F`),
`core/data_loader.py` is `import yfinance as yf`, and `data_cache/` holds
Yahoo-derived files. Nothing is needed from you to switch: the data is free,
no account, and Node.js is installed. Purely waiting on decisions #1/#2.

---

## 4. Owed work (open engineering, not decisions)

- **Entry slippage.** The engine slips stop *exits* but not *entries* — the
  last gap in Issue #3's cost model. Deferred deliberately: changing entry
  fills moves the 127-trade regression baseline every test checks against, so
  it belongs in the #3 engine session (with the baseline updated on purpose).
- **Task 5 of Issue #3** — the diagnostic report with a reliability rating —
  is the one #3 task still outstanding.
- **The other three dashboard pages** (Compare / Tracker / Settings) are
  intentional stubs, waiting on your spec. Backend endpoints for all three
  already exist and are tested.

---

## 5. Minor latent issues found in the 2026-07-16 cleanup audit

Neither is worth a risky fix now; recorded so they're not forgotten.

- **`core/strategies.py` `load_errors` is a module global** cleared and
  refilled on every scan. Under Flask's threaded dev server two concurrent
  `/api/strategies` requests could interleave on it. Self-healing (both scan
  the same folder → same result) and cosmetic (only the error list), so very
  low severity. Clean fix: have `load_strategies()` return its errors instead
  of mutating a global — a small refactor across `app.py`, `get_strategy`, and
  the tests.
- **`_covering_cache` compares ISO date strings lexically.** Correct for every
  real call path (the API normalises dates via `strftime`), but a raw CLI call
  with a non-zero-padded date like `2015-1-1` would compare wrong. Normalise
  in `get_data` if we ever accept unsanitised CLI dates.

---

## 6. Things I decided so you can overrule them

- **`volume` is NULL for backtest trades.** You asked for lot size in the
  journal schema, but the engine models price, not position size. NULL is the
  honest answer until the sizing layer (`core/account.py`) is wired into the UI.
- **Compare's saved runs are keyed by strategy + params** (not name alone), so
  MA20 and MA50 don't overwrite each other — implemented that way in the API.
- **Drawdown has no colour** on the dashboard: no honest threshold says which
  number is bad — it's context, not a verdict.
- **Win-rate colour is relative to break-even**, not a fixed 40/60 — that would
  call a profitable 39% run "red".
- **The dashboard is deliberately dependency-free** (hand-drawn SVG chart, no
  chart library, no CDN, no build step). It works offline; a feature, not a gap.
- **Nav items** are Backtest / Compare / Tracker / Settings. "Notes" was cut
  (project docs, not a page); "Journal" became "Tracker".

---

*Resolved since the last version (2026-07-15), for the record:* the 6 stashed
fixes were applied; the dead x-axis code, silent startup failures, null
`exit_reason`, unescaped `innerHTML`, and Run-button bugs were fixed and
verified in-browser; margin/account tracking was built (`core/account.py`);
engine v3/v4 features and the API now have committed tests; `results/*.csv`
were regenerated to the 14-column schema; the 8 diagnosis issues were
published (#5–#12); the exit panel was visually verified.
