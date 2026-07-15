# Flagged

Things I raised during the work that need **your decision**, or that you
should know before trusting a number or spending money. Not a bug list —
that's `docs/system-diagnosis.md`. Not design notes — that's `docs/notes.md`.

Last updated: 2026-07-15

---

## 1. Decisions waiting on you

| # | Decision | My recommendation |
|---|----------|-------------------|
| 1 | **The 6 stashed fixes** — dead code removal, quiet `summarize()`, hex colours, stale docstring. They're in `git stash` because Issue #4 asked for a diagnosis, not repairs. | `git stash pop` and let me finish + test them as their own piece of work. They're all Action Plan items. |
| 2 | **Compare storage key** — you said one saved result per strategy, re-running replaces it. Keyed by strategy *name*, MA20 and MA50 overwrite each other, so you could never compare a strategy against its own tuning — which is the cheap way to spot overfitting. | Key by **strategy + params**. Your no-duplicates rule survives intact, just with a finer key. |
| 3 | **Dukascopy switch: daily or intraday first?** | **Daily first.** Changing the data source *and* the timeframe at once means you can't tell which caused the change in results. |
| 4 | **Keep Yahoo after the switch?** | Yes — add a `source` field to the pair registry rather than ripping yfinance out. Costs nothing, lets us compare sources. |
| 5 | **Broker for the Tracker page.** Undecided. | OANDA is the front-runner (good REST API, free practice account, and we may want their bid/ask data anyway). Not committed — worth a conversation. |
| 6 | **Publishing the 8 diagnosis issues.** `gh` works in your terminal but not in the shell I run commands in, and I won't take your token out of the keychain. | Run once: `python3 scripts/create_issues.py --create` |

---

## 2. Warnings — the ones that could cost real money

### ⚠️ Every result you've seen is in-sample
The parameters (MA 20, 100/200 pip stop/target, 10-day hold) were never
validated on data they weren't chosen against. **This is the single biggest
gap between "interesting" and "believable"**, and it's nearly free to close:
tune on 2015–2020, then run 2021–2024 **once**, untouched. If the edge
survives, it's real. Also check parameter neighbours (MA 15/25, SL 80/120) —
a real edge degrades gently, a fluke collapses.

### ⚠️ Sample size is small enough to fool you
127 trades per pair carries roughly **±8 percentage points** of pure noise on
the win rate. A tweak that "improves" win rate by a few points is
indistinguishable from luck. Any subgroup claim ("stop-outs in 2019") means
essentially nothing.

### ⚠️ The current edge is thin-to-negative on this data
Latest 4-pair run: **39.6% win rate against a 39.7% break-even** — a tenth of
a point *below* water, expectancy **−0.001R**. Individually, GBPUSD and gold
showed a small positive edge; EURUSD and USDJPY didn't. This is after spread
but **before** swap/financing costs, which aren't modelled yet.

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
the engine's envelope rule exists to defend against exactly this), indicative
rather than traded quotes, and **gold is the GC=F futures proxy, not spot**.

---

## 3. Data source status: still Yahoo, nothing switched

Checked 2026-07-15 — **no part of the Dukascopy plan is implemented**:
- `core/pairs.py` tickers are Yahoo symbols (`EURUSD=X`, `GC=F`)
- `core/data_loader.py` is `import yfinance as yf`, nothing else
- `data_cache/` holds Yahoo-derived files
- No Dukascopy code exists outside the plan in `docs/notes.md`

Nothing is needed from you to switch: the data is **free, no account, no
card**, and Node.js (v26) is already installed for the downloader. It's
purely waiting on decisions #3 and #4 above.

---

## 4. Owed work / known-unverified

- **The exit panel resize was never visually checked.** A tooling outage
  blocked every browser action but screenshots the day it shipped. The CSS
  was verified served and the flex maths re-derived, but it owes one look.
  Everything else in the dashboard was driven and verified in-browser.
- **Engine v4's best features have no repo tests.** Shorts, trailing stops,
  break-even, limit entries, exit signals, position cap, ambiguity policy,
  commission/slippage/swap — all verified once in throwaway scratchpad
  scripts (independent shadow implementation agreeing on 1,980 trades across
  300 random markets), none of it committed. The strongest part of the system
  is the least protected.
- **Margin/free-margin tracking doesn't exist** — the one genuinely missing
  piece of Issue #3. It belongs in the position-sizing layer, not the engine.
- **The equity chart has no x-axis labels** — `renderEquity()` builds them and
  never inserts them into the SVG. Dead code, unlabelled axis.
- **`results/*.csv` are stale** — v3 schema (9 cols); the engine now emits 14.

---

## 5. Things I decided so you can overrule them

- **`volume` is NULL for backtest trades.** You asked for lot size in the
  journal schema, but the engine models price, not position size. NULL is the
  honest answer until the sizing layer exists.
- **Drawdown has no colour** on the dashboard. Every strategy has one and
  there's no honest threshold that says which number is bad — it's context,
  not a verdict.
- **Win-rate colour is relative to break-even**, not your original fixed
  40/60 thresholds — those would have called a profitable 39% run "red".
- **The dashboard is deliberately dependency-free** (hand-drawn SVG chart, no
  chart library, no CDN, no build step). It works offline and we own every
  pixel. That's a feature at this scale, not a gap.
- **Nav items** are Backtest / Compare / Tracker / Settings. "Notes" was cut
  (project docs, not a page); "Journal" became "Tracker".
