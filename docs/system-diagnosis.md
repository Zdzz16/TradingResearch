# System Diagnosis — full-repo sweep (2026-07-15)

Response to GitHub Issue #4 ("system diagnosis"). Every finding, grouped by
sector; each sector below is a self-contained, copy-pasteable GitHub issue in
the requested format. Severity tags: 🔴 broken/wrong, 🟡 debt/risk, 🟢 upgrade.

**What the sweep did NOT find** (said out loud, per zero-tolerance): no broken
imports or routes (27 tests green, API smoke-tested end-to-end), no unused
imports (AST scan across every module), no hardcoded absolute paths, no unused
dependencies beyond the matplotlib nuance below, no security exposure (server
binds 127.0.0.1, debug off), and no performance problem — the full 4-pair
pipeline runs in **46 ms**, so "make it async/faster" style modernisation is
explicitly NOT recommended; it would add complexity and solve nothing.

---

## [System Cleanup & Upgrade] Core Engine & Tests

### Everything Broken or Unneeded in This Sector
- 🔴 **The deep verification suites are not in the repo.** `core/engine.py`
  (v4) was verified with an independent shadow implementation (1,980-trade
  agreement across 300 random markets), randomized invariant sweeps, and ~40
  hand-computed scenario checks — but those lived in throwaway scratchpad
  scripts, and the worktree session meant to port them produced **zero
  commits** (see Root sector). `tests/test_engine.py` (19 tests) covers only
  v2-era behaviour: **nothing exercises shorts (`Direction`), trailing/
  break-even stops, per-signal `StopDistance`/`TargetDistance`, `EntryLimit`,
  `ExitSignal`, `max_open_trades`, `ambiguous_policy`, `commission_pct`,
  `slippage`, `swap_per_night`, or the envelope rule.** The engine's strongest
  features are its least protected.
- 🟡 No golden-file regression test: the "EURUSD must reproduce its 127
  committed trades bit-for-bit" check has been run by hand at every refactor;
  nothing runs it automatically.
- 🟢 Documented simplifications (not bugs, listed for honesty): swap is the
  same both directions; slippage applies to stop fills only; MAE/MFE measured
  on full bars; same-bar stop+target order unknowable (flagged `ambiguous`).

### Where We Are Behind & Upgrade Opportunities
- Port the verification suites into `tests/` (per lean-files preference: fold
  into `tests/test_engine.py` + one shadow-agreement file, not five).
- Golden-file test pinned to the committed `data_cache/` snapshot.
- Overlap with Issue #3: look-ahead bias is already audited (entry at next
  open; prior-bar trailing updates; fill-bar target suppression on limit
  entries), and spread/slippage modelling exists with a different-but-
  equivalent convention to the one Issue #3 sketches (full spread once per
  round trip rather than half-spread per side — same cost, one knob).
  **Margin/free-margin tracking is the one genuinely missing piece** — per
  the agreed architecture it belongs in the position-sizing layer that walks
  the trade list, not inside the engine loop. Decide there, not here.

### Action Plan
- [ ] Fold v3/v4 feature tests (shorts, trailing, BE, limit entries, exit
      signals, cap, policy, costs, envelope) into `tests/test_engine.py`
- [ ] Add shadow-implementation agreement test (seeded, ~300 random markets)
- [ ] Add golden-file regression test (EURUSD, bit-exact,
      `float_precision='round_trip'`)
- [ ] Build the account/equity/margin simulator as a post-processing layer
      (consumes `r_multiple`; blocks trades when margin insufficient) — the
      Issue #3 item that actually needs new code

---

## [System Cleanup & Upgrade] Data Layer

### Everything Broken or Unneeded in This Sector
- 🔴 **`results/*.csv` are stale**: all four committed files have the 9-column
  v3 schema; engine v4 outputs 14 columns (`direction`, `entry_type`,
  `days_held`, `mae`, `mfe` missing). Anyone reading them gets yesterday's
  shape with no warning. Regenerate or delete.
- 🟡 `core/data_loader.py` cache never invalidates: a partial/interrupted
  download would be cached forever and silently reused. Fine for the
  committed, verified snapshots; wrong the day a new range is fetched badly.
- 🟡 `CACHE_DIR = "data_cache"` is cwd-relative (as is `results/` in
  `run_backtest.py`): the dashboard works because it `os.chdir`s to root; a
  CLI run from any other directory recreates the cache elsewhere and
  re-downloads everything. Anchor via `Path(__file__)`.
- 🟡 `core/pairs.py` stores colours as matplotlib names (`"tab:blue"`), which
  forces `matplotlib` to be imported by the **web server** solely to convert
  them to hex. Store hex strings directly; matplotlib then belongs only to
  the optional CLI chart.

### Where We Are Behind & Upgrade Opportunities
- **Data quality is the known ceiling**: Yahoo FX bars carry 30–82 incoherent
  rows per pair (engine's envelope rule defends), gold is the GC=F futures
  proxy, quotes are indicative. The upgrade path is already decided and
  costs nothing (docs/notes.md): Dukascopy tick/daily data first, keyed by a
  new `source` field per pair so Yahoo remains available for comparison.
- Date range is hardcoded (`START, END` in run_backtest.py) and the dashboard
  has no date controls — also the prerequisite for the in-sample/out-of-
  sample split that makes any result believable.

### Action Plan
- [ ] Regenerate the four `results/*.csv` with the v4 engine (or delete them
      and document that results/ is CLI-run output only)
- [ ] Anchor `data_cache/` and `results/` paths to the project root
- [ ] Store hex colours in `core/pairs.py`; drop matplotlib from the web path
- [ ] Add `source` field to the registry + Dukascopy loader (daily first)
- [ ] Date-range parameters through API + sidebar (enables IS/OOS split)

---

## [System Cleanup & Upgrade] Strategy System

### Everything Broken or Unneeded in This Sector
- 🔴 Stale docstring: `run_backtest.py` still says *"which entry in
  core/strategies.py STRATEGIES to run"* — that registry was replaced by
  `/strategies` folder discovery (commit ef2ce2c). Doc lies about the system.
- 🟢 Nothing else — this sector is hours old (Issue #2), has 8 dedicated
  tests including broken-file isolation, and re-scans per call **by design**
  (that's what makes drop-in files appear on refresh; at 46 ms/run the cost
  is irrelevant).

### Where We Are Behind & Upgrade Opportunities
- Only one strategy exists. The engine supports per-signal `Direction`,
  `StopDistance`/`TargetDistance` (ATR-ready), `EntryLimit`, `ExitSignal` —
  and **no strategy uses any of them yet**. A second strategy (e.g. RSI
  reversal or breakout) proves the discovery system for real, gives the
  Compare tab a reason to exist, and should exercise at least one per-signal
  column so that engine capability stops being theoretical.

### Action Plan
- [ ] Fix the stale docstring in `run_backtest.py`
- [ ] Add a second strategy file that uses ≥1 per-signal column
- [ ] Settle the Compare storage key (strategy name vs **name+params** —
      recommendation: name+params, see docs/notes.md) so runs can be saved

---

## [System Cleanup & Upgrade] Analysis & Plotting

### Everything Broken or Unneeded in This Sector
- 🔴 **`plot_equity_curve()` in `core/plotting.py` is dead code** — zero
  callers since the multi-pair chart replaced it. Delete.
- 🟡 **`summarize()` prints 12 lines unconditionally** — including on every
  dashboard API call (×4 pairs per Run click), spamming the server console.
  It needs a `verbose` switch; the dashboard passes quiet.
- 🟡 **Analysis logic is leaking into the API layer**: `avg_win_r`,
  `avg_loss_r` and `breakeven_win_rate` are computed inside
  `dashboard/app.py`. That's `core/analysis.py`'s job — as written, the CLI
  and any future consumer don't get those numbers.

### Where We Are Behind & Upgrade Opportunities
- `plt.show()` blocks the CLI run; an optional save-to-file flag would let
  headless runs keep a chart artifact.
- Candidate metrics when Compare lands: profit factor, drawdown duration,
  per-pair rows inside a pooled summary. Add only what earns its place.

### Action Plan
- [ ] Delete `plot_equity_curve()`
- [ ] `summarize(trades, label, verbose=True)`; dashboard calls verbose=False
- [ ] Move avg-R / break-even-win-rate math from `dashboard/app.py` into
      `core/analysis.py` so every consumer gets the same numbers

---

## [System Cleanup & Upgrade] Journal

### Everything Broken or Unneeded in This Sector
(Entire sector is scheduled for scrap-and-rebuild — GitHub Issue #1. Listed
for completeness so this sweep is total.)
- 🔴 `core/journal.py::close_trade()` with a wrong index **silently creates a
  phantom row** (pandas `.loc` enlargement) in what is meant to be the
  real-money record. Known since the first review; still live.
- 🔴 `log_trade.py` logs a hardcoded example trade on every run — re-running
  duplicates it.
- 🟡 `JOURNAL_PATH` is cwd-relative; schema is unstable (exit columns appear
  only after the first `close_trade`).
- 🟡 `journal/trade_journal.csv` contains one test entry — **user has
  approved deleting it** as part of the rebuild.

### Where We Are Behind & Upgrade Opportunities
Issue #1's split design (backtest journal + live journal, one schema, SQLite
or JSON storage, `broker_sync.py` placeholder) supersedes everything here.
One addition from the Tracker plan (docs/notes.md): log the **intended stop
distance at entry**, because `r_multiple` can't be computed later without it
and the broker API won't supply it.

### Action Plan
- [ ] Implement Issue #1 as specced (journal/ package, two stores, one schema)
- [ ] Delete `core/journal.py`, `log_trade.py`, `journal/trade_journal.csv`
- [ ] Include `intended_stop_distance` in the live schema

---

## [System Cleanup & Upgrade] Backend API & Pipeline

### Everything Broken or Unneeded in This Sector
- 🟡 `run_backtest.py` writes `results/` relative to cwd (see Data sector).
- 🟡 `dashboard/app.py` imports matplotlib for hex conversion only (see Data
  sector — fix lives in pairs.py).
- 🟡 Server console noise from `summarize()` prints (see Analysis sector).
- 🟢 No `/favicon.ico` route → one 404 log line per browser session. Trivial.

### Where We Are Behind & Upgrade Opportunities
- Flask's dev server is correct for a localhost tool (bound to 127.0.0.1,
  debug off). **If** this is ever exposed beyond the machine, switch to
  waitress/gunicorn and add auth — noted so it's a decision, not an accident.
- `/api/backtest` is synchronous; cached ranges answer in ~50 ms, but a
  fresh-range Yahoo download can block for seconds with no progress feedback.
  Acceptable now; revisit when date-range controls land.
- Compare needs a saved-runs store (in-memory dict is enough — runs are 15 ms
  and deterministic; it's a convenience cache, not a source of truth).

### Action Plan
- [ ] Anchor results/ path; quiet summarize; registry hex colours (all above)
- [ ] Add favicon (one-line route or inline data-URI in the template)
- [ ] Saved-runs store keyed by strategy+params (pending user's key decision)

---

## [System Cleanup & Upgrade] Frontend UI

### Everything Broken or Unneeded in This Sector
- 🟡 The exit-panel resize (commit 4d9eabc) was shipped **without its final
  in-browser visual check** — the safety classifier outage blocked
  everything but screenshots that day. CSS was verified served correctly +
  flex math re-derived; still owes one human/browser look.
- 🟢 Compare / Tracker / Settings are intentional stubs (blank page + label),
  not junk. Recorded so a future sweep doesn't misread them.
- 🟢 Vanilla HTML/CSS/JS with a hand-drawn SVG chart and zero build step is a
  **feature** at this scale (offline, no CDN, no toolchain) — explicitly not
  a "we're behind React" finding.

### Where We Are Behind & Upgrade Opportunities
- Last-run settings (pairs, params, risk) aren't persisted — a page reload
  forgets them. localStorage, ~10 lines, big quality-of-life.
- Custom pair checkboxes aren't keyboard-accessible (divs, not inputs).
- No date-range control (see Data sector; same item).
- Chart could show hover tooltips (values per trade) — nice-to-have.

### Action Plan
- [ ] One visual pass over the exit panel at desktop width
- [ ] Persist sidebar settings in localStorage
- [ ] Keyboard/a11y pass on the pair list
- [ ] Date-range picker (with the API work)

---

## [System Cleanup & Upgrade] Root, Config & Repo Hygiene

### Everything Broken or Unneeded in This Sector
- 🔴 **Dead worktree**: `.claude/worktrees/friendly-shtern-f46823/` is a full
  duplicate of the project (25 files incl. copies of all four data caches and
  the old journal) from a task session that produced **0 commits** and a
  clean tree — verified contentless. The branch
  `claude/friendly-shtern-f46823` points at an ancestor of master. Remove
  both; nothing is lost.
- 🟡 **No README.md** — the repo is on GitHub with no explanation of what it
  is, how to run the dashboard, or how to add a strategy.
- 🟡 **No CI** — 27 tests exist and nothing runs them automatically. A
  GitHub Actions workflow (pytest on push, ~15 lines) makes every future
  push self-checking; with the verification suites ported (Engine sector),
  CI becomes the engine's permanent guarantee.
- 🟢 `conftest.py` is empty and looks like junk but is **load-bearing** (it
  makes pytest put the project root on sys.path). Needs a one-line comment
  saying so, or it'll be "cleaned up" someday and break the suite.
- 🟢 `__pycache__/` dirs on disk — gitignored, regenerated, cosmetic only.
- 🟢 `.claude/launch.json` is committed intentionally (documents how the
  dashboard is launched). Not junk.

### Where We Are Behind & Upgrade Opportunities
- Dependencies are honest: 5 direct, all pinned, all imported (verified by
  scan). matplotlib becomes CLI-only once pairs.py stores hex — keep it, but
  it stops being a web-server dependency.
- Optional: `pyproject.toml` to declare the Python floor (3.14 in use) and
  centralise tool config. No packaging need yet — this isn't a library.
- No LICENSE — fine for a personal repo; add one only if it should be public
  in a real sense.

### Action Plan
- [ ] `git worktree remove` friendly-shtern + delete its branch
- [ ] Write README.md (what/why, quickstart, dashboard, adding a strategy)
- [ ] Add `.github/workflows/tests.yml` running pytest on push
- [ ] Comment conftest.py's purpose
- [ ] Regenerate stale results/ (Data sector item, listed once)
