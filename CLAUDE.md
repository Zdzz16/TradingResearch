# TradingResearch

Long-term memory for this project. Read this first — it says what this is,
how it's built, how to work here, and where everything else lives.

## What this is

A forex strategy research platform, built solo by **Filip**, who is learning
Python alongside it. It backtests trading strategies on historical price data,
sizes them against a real account, journals the results, and presents all of it
in a self-built web dashboard.

**The goal is not more features — it's a strategy Filip can trust enough to
trade real money on.** Current honest state: the one strategy's edge is
thin-to-negative after costs, and has only ever been tested in-sample. Say so
plainly; don't dress up results.

## Stack

- **Python** — pandas, Flask, SQLite. Node.js for the Dukascopy downloader.
- **No frontend framework.** The dashboard is hand-written HTML/CSS/JS with a
  hand-drawn SVG chart — no React, no chart library, no build step, no CDN.
  This is deliberate: it works offline and we own every pixel. Streamlit was
  tried and scrapped because of its unremovable chrome.
- **Dependencies are few and pinned** (`requirements.txt`). Adding one is a
  decision, not a reflex.
- **123 tests, all green.** Run `python3 -m pytest tests/ -q` before committing.

## How it fits together

```
data_loader  →  strategies/  →  engine  →  analysis   →  dashboard
(Dukascopy)     (drop-in .py)   (trades)   (stats/R)     (Flask + JS)
                                    ↓
                              account.py  (sizing, margin)
                              journal/    (backtest + live trades)
```

- `run_backtest.run_strategy()` is the **one entry point** for a single
  backtest. The CLI and the dashboard both call it, so they can't drift apart.
- **Adding a strategy** = drop a `.py` file in `strategies/` with a
  `generate_signals()` function. It appears in the UI automatically. Nothing
  to register. See `strategies/ma_crossover.py` for the contract.
- Instruments live in `core/pairs.py` (4: EURUSD, GBPUSD, USDJPY, XAUUSD).

## Rules of engagement — how to work with Filip

These were learned the hard way. Breaking them wastes his time.

1. **Ask before building. Then build.** Do not run ahead and produce work he
   didn't ask for — especially UI. Use AskUserQuestion, get the answer, then
   act. "Work with me, don't just do shit."
2. **He decides how it looks.** UI is his call. Don't restyle or restructure
   unprompted, and don't treat a first version as final.
3. **Verify, don't eyeball.** Drive the real browser and *measure* (widths,
   visibility, counts). A screenshot that looks right can hide a hidden
   element — that's happened. Say what was actually checked.
4. **Be honest, especially about bad news.** If a result got worse, lead with
   it. If something wasn't verified, say so. Never claim a check that wasn't run.
5. **Keep the file count lean.** Extend existing files rather than adding new
   ones. He hates sprawl.
6. **Report in chat.** Ratings and reviews go in the message, not a file.
7. **Re-read before re-reviewing.** He runs parallel Claude sessions, so the
   code may have changed since your last read. Check `git log` first.
8. **Never delete his data** — `journal/`, `data_cache/`, `results/`.

## Hard rules — don't break these

- **Run the tests before committing.** Every time.
- **The engine is verified**; it has an independent shadow implementation and
  a proven absence of look-ahead bias. Changing exit logic means re-proving it.
- **Regression baseline: EURUSD = 129 trades** (was 127 on Yahoo). If that
  number moves, understand exactly why before accepting it.
- **Dukascopy ships calendar-day bars** — flat Saturday placeholders and
  partial Sunday sessions. `_to_trading_days()` fixes this. Without it a
  "20-bar" MA silently spans 20 *calendar* days.
- **Gold is real spot** (Dukascopy `xauusd`), no longer the GC=F futures proxy.
- **The journal holds real-money records.** Treat it as production data.
- Costs are modelled explicitly: spread, commission, swap, slippage.
  Results are quoted in **R** (multiples of risk) because price units aren't
  comparable across pairs.

## Where everything else lives

- **[docs/roadmap.md](docs/roadmap.md)** — what we're building and why, with
  effort tags and a suggested order. The plan.
- **[docs/flagged.md](docs/flagged.md)** — open decisions waiting on Filip, and
  the warnings that matter before risking money (every result so far is
  in-sample; the edge is thin). **Read this before trusting a number.**
- **[docs/changelog.md](docs/changelog.md)** — one short line per change, by
  day. Append to it every session.
- **[docs/auto-memory.md](docs/auto-memory.md)** — **auto memory keeping**: the
  rule that the project's memory and docs must be kept current *without being
  asked*, what belongs where, and the end-of-session check. Follow it.
- **GitHub issues #5–#12** — outstanding cleanup work, by sector.

## Current focus

Dashboard. The **Backtest** page is complete. **Compare** has a first version
that is explicitly **not final** — Filip will direct how it should look.
**Tracker** and **Settings** are still stubs.
