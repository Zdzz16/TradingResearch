# System Diagnosis — full-repo sweep

Deliverable for GitHub Issue #4. **Two independent audit passes** were run over
the whole repo; the second pass found 8 items the first missed (all merged in
below, marked 🆕).

## How to use this (lazy mode)

Each sector below gives you a **title line** and a **fenced body block**.
On GitHub, hover the body block → click the copy icon → New Issue → paste the
title, paste the body. Eight sectors = eight issues, no editing needed.

## Severity key
🔴 broken / wrong · 🟡 debt / risk · 🟢 upgrade opportunity

## What the sweep did NOT find (stated so "clean" means something)
- No unused imports anywhere (AST scan over every module)
- No unused CSS classes (every class in style.css is used) 🆕
- No TODO/FIXME/commented-out dead code 🆕
- No hardcoded absolute paths, no secrets, no exposed bind (127.0.0.1, debug off)
- No performance problem: the full 4-pair pipeline runs in **46 ms**. Async/
  worker/React-style "modernisation" is explicitly **not** recommended — it
  would add complexity and fix nothing.

---

## Sector 1 — Core Engine & Tests

**Issue title:**
`[System Cleanup & Upgrade] Core Engine & Tests`

**Issue body:**

```markdown
### Everything Broken or Unneeded in This Sector

- 🔴 **The engine's best features have zero test coverage.** `core/engine.py`
  (v4) supports shorts (`Direction`), trailing stops, break-even stops,
  per-signal `StopDistance`/`TargetDistance`, `EntryLimit`, `ExitSignal`,
  `max_open_trades`, `ambiguous_policy`, `commission_pct`, `slippage`,
  `swap_per_night` and the envelope rule. **`tests/test_engine.py` (19 tests)
  exercises none of them** — it only covers v2-era behaviour. The deep
  verification (independent shadow implementation agreeing on 1,980 trades
  across 300 random markets; ~40 hand-computed scenarios) was run in
  throwaway scratchpad scripts that were never committed, and the worktree
  session meant to port them produced **0 commits**. The strongest part of
  the system is the least protected part.
- 🔴 **Four modules have no tests at all**: `core/analysis.py`,
  `core/data_loader.py`, `core/journal.py`, `core/plotting.py`. Every number
  the dashboard shows comes out of `analysis.py`.
- 🟡 **No golden-file regression test.** "EURUSD must still reproduce its 127
  committed trades bit-for-bit" has been verified by hand at every refactor;
  nothing enforces it automatically. Note it requires
  `pd.read_csv(..., float_precision='round_trip')` — the default parser is
  not round-trip exact and will report false differences.
- 🟢 Documented simplifications, listed for honesty, not bugs: swap is the
  same both directions; slippage applies to stop-type fills only; MAE/MFE are
  measured on full bars; same-bar stop+target order is unknowable from daily
  data (flagged via the `ambiguous` column).

### Where We Are Behind & Upgrade Opportunities

- Port the verification suites into `tests/` so they run on every change.
- Add a golden-file regression test pinned to the committed `data_cache/`
  snapshot.
- **Overlap with Issue #3 (engine verification)** — most of it is already
  done: look-ahead bias is audited (entry at next open, prior-bar trailing
  updates, fill-bar target suppression on limit entries), and spread/slippage
  modelling exists with an equivalent-but-different convention to the one
  Issue #3 sketches (one full spread per round trip rather than half-spread
  per side — same cost, one knob). **Margin / free-margin tracking is the one
  genuinely missing piece**, and per the agreed architecture it belongs in the
  position-sizing layer that walks the finished trade list, not inside the
  engine loop.

### Action Plan

- [ ] Fold v3/v4 feature tests into `tests/test_engine.py` (shorts, trailing,
      break-even, limit entries, exit signals, position cap, ambiguity policy,
      commission/slippage/swap, envelope rule)
- [ ] Add the shadow-implementation agreement test (seeded, ~300 random markets)
- [ ] Add the golden-file regression test (EURUSD, bit-exact, round_trip)
- [ ] Add tests for `core/analysis.py` (the stats every card displays)
- [ ] Build the account/equity/margin simulator as a post-processing layer
      (consumes `r_multiple`; refuses trades when free margin is insufficient)
```

---

## Sector 2 — Data Layer

**Issue title:**
`[System Cleanup & Upgrade] Data Layer`

**Issue body:**

```markdown
### Everything Broken or Unneeded in This Sector

- 🔴 **`results/*.csv` are stale.** All four committed files carry the 9-column
  v3 schema; engine v4 emits 14 columns — `direction`, `entry_type`,
  `days_held`, `mae`, `mfe` are missing. Anyone reading them gets yesterday's
  shape with no warning that it's outdated.
- 🟡 **The data cache never invalidates.** `core/data_loader.py` treats any
  existing cache file as good forever. A partial or interrupted download would
  be cached and silently reused for every future run. Safe today only because
  the committed snapshots are known-good.
- 🟡 **Cache read assumes its own columns exist**: the cached-path
  `dropna(subset=["Open","High","Low","Close"])` raises `KeyError` on a
  malformed cache file instead of reporting a bad cache.
- 🟡 **cwd-relative paths.** `CACHE_DIR = "data_cache"` and `results/` in
  `run_backtest.py` resolve against the working directory. The dashboard only
  works because it calls `os.chdir(ROOT)` on import; a CLI run from any other
  directory silently creates a second cache elsewhere and re-downloads
  everything.
- 🟡 **Colours are stored as matplotlib names** (`"tab:blue"`) in
  `core/pairs.py`, which forces the **web server** to import matplotlib purely
  to convert them to hex. Store hex directly; matplotlib then belongs only to
  the optional CLI chart.

### Where We Are Behind & Upgrade Opportunities

- **Data quality is the known ceiling.** Yahoo FX bars contain 30–82
  incoherent rows per pair (Open/Close outside the High–Low range — the
  engine's envelope rule exists to defend against exactly this), gold is the
  `GC=F` futures proxy rather than real spot, and quotes are indicative rather
  than traded. The upgrade path is decided and free (see `docs/notes.md`):
  Dukascopy tick/daily data, added behind a new `source` field per pair so
  Yahoo stays available for comparison. Node.js is already installed; no
  account or payment is needed.
- **The date range is hardcoded** (`START, END` in `run_backtest.py`) and the
  dashboard has no date controls — which also blocks the in-sample /
  out-of-sample split that would make any result believable.

### Action Plan

- [ ] Regenerate the four `results/*.csv` with the v4 engine, or delete them
      and document that `results/` is CLI output only
- [ ] Anchor `data_cache/` and `results/` to the project root via `Path(__file__)`
- [ ] Validate cached files on read; re-download instead of `KeyError`
- [ ] Store hex colours in `core/pairs.py`; drop matplotlib from the web path
- [ ] Add a `source` field + Dukascopy loader (daily bars first, so the change
      is apples-to-apples against Yahoo)
- [ ] Thread date-range through the API and sidebar (enables IS/OOS split)
```

---

## Sector 3 — Strategy System

**Issue title:**
`[System Cleanup & Upgrade] Strategy System`

**Issue body:**

```markdown
### Everything Broken or Unneeded in This Sector

- 🔴 **Stale docstring lies about the architecture.** `run_backtest.py` still
  says *"which entry in core/strategies.py STRATEGIES to run"*. That hardcoded
  registry no longer exists — strategies are discovered from the `/strategies`
  folder (commit ef2ce2c).
- 🟢 Nothing else. This sector is hours old, has 8 dedicated tests including
  broken-file isolation, and re-scans the folder on every call **by design** —
  that's what makes a dropped-in file appear on refresh, and at 46 ms/run the
  cost is irrelevant.

### Where We Are Behind & Upgrade Opportunities

- **Only one strategy exists.** The engine supports per-signal `Direction`,
  `StopDistance`/`TargetDistance` (ATR-ready), `EntryLimit` and `ExitSignal` —
  and **no strategy uses any of them**. A second strategy (RSI reversal,
  breakout, anything structurally different) would prove the discovery system
  for real, give the Compare tab a reason to exist, and turn engine capability
  from theoretical into exercised.
- **Compare needs a storage decision** (open question, `docs/notes.md`): saved
  runs keyed by strategy *name* means MA20 and MA50 overwrite each other, so
  you could never compare a strategy against its own tuning — which is the
  cheap way to spot overfitting (a real edge degrades gently across
  neighbouring settings; a fluke collapses). Recommendation: key by
  **strategy + params**; the no-duplicates rule still holds with a finer key.

### Action Plan

- [ ] Fix the stale docstring in `run_backtest.py`
- [ ] Add a second strategy file that uses at least one per-signal column
- [ ] Decide the Compare storage key (recommend: strategy + params)
```

---

## Sector 4 — Analysis & Plotting

**Issue title:**
`[System Cleanup & Upgrade] Analysis & Plotting`

**Issue body:**

```markdown
### Everything Broken or Unneeded in This Sector

- 🔴 **`plot_equity_curve()` in `core/plotting.py` is dead code** — zero
  callers since the multi-pair chart replaced it.
- 🟡 **`summarize()` prints 12 lines unconditionally**, including on every
  dashboard API call (×4 pairs per Run click), spamming the server console. It
  needs a `verbose` switch that the dashboard sets to False.
- 🟡 **Analysis maths has leaked into the API layer.** `avg_win_r`,
  `avg_loss_r` and `breakeven_win_rate` are computed inside
  `dashboard/app.py`. That belongs in `core/analysis.py` — as written, the CLI
  and any future consumer don't get those numbers, and the two paths can drift.
- 🟡 **`avg_win` / `avg_loss` are meaningless when pooled across pairs.**
  `summarize()` averages them in raw price units, so a multi-pair run averages
  gold's dollars with EURUSD's pips. The R-based versions are correct; the
  price-unit ones should be per-pair only, or dropped from pooled output.

### Where We Are Behind & Upgrade Opportunities

- `plt.show()` blocks the CLI run; an optional save-to-file flag would let
  headless runs keep a chart artifact.
- Candidate metrics once Compare lands: profit factor, drawdown duration,
  per-pair rows inside a pooled summary. Add only what earns its place — the
  brief is "don't get lost in numbers".

### Action Plan

- [ ] Delete `plot_equity_curve()`
- [ ] `summarize(trades, label, verbose=True)`; dashboard passes verbose=False
- [ ] Move avg-R and break-even-win-rate maths into `core/analysis.py`
- [ ] Make pooled price-unit averages per-pair or drop them
```

---

## Sector 5 — Frontend UI

**Issue title:**
`[System Cleanup & Upgrade] Frontend UI`

**Issue body:**

```markdown
### Everything Broken or Unneeded in This Sector

- 🔴 🆕 **The equity chart has no x-axis labels, and the code that builds them
  is dead.** `dashboard/static/app.js` `renderEquity()` builds an `xLabels`
  string of trade-number `<text>` elements (lines ~271–275) and then **never
  interpolates it into the SVG template** (line ~283 emits only
  `${grid}${zero}${lines}`). Verified by inspection: the variable is assigned
  and never read. The chart has been shipping with an unlabelled x-axis.
- 🔴 🆕 **Leftover placeholder markup**: the same SVG template ends with an
  empty `<text ... opacity="0"></text>` element that renders nothing.
- 🟡 🆕 **Silent failure on API errors at startup.** `loadPairs()` and
  `loadStrategies()` have no `try/catch` and are never awaited. If `/api/pairs`
  or `/api/strategies` fails, the promise rejects unhandled, `PAIRS` stays
  empty, and the sidebar is simply blank with no message — the user cannot
  tell a broken backend from an empty one.
- 🟡 🆕 **`renderTrades()` will throw on a null `exit_reason`**
  (`t.exit_reason.replace(...)`). The engine always sets one today, so this is
  latent rather than live — but it's one API change away from a blank page.
- 🟡 🆕 **Unescaped interpolation into `innerHTML`** for strategy `label` /
  `description` and pair names. These come from local files you write, so it
  isn't a live attack vector — but it's a bad habit to set before any of this
  is ever fed by remote data (broker API, Tracker page).
- 🟡 🆕 **Run button can be wrongly re-enabled.** If no strategy files exist,
  `loadStrategies()` disables Run — but `run()`'s `finally` block
  unconditionally re-enables it.
- 🟡 The exit-panel resize (commit 4d9eabc) shipped **without its final
  in-browser visual check** — a tooling outage blocked everything but
  screenshots that day. CSS was verified served and the flex maths re-derived;
  it still owes one look.
- 🟢 Compare / Tracker / Settings are intentional stubs (blank page + label),
  not junk — recorded so a future sweep doesn't "clean them up".
- 🟢 Vanilla HTML/CSS/JS with a hand-drawn SVG chart and no build step is a
  **feature** at this scale (works offline, no CDN, no toolchain). Explicitly
  not a "we're behind React" finding.

### Where We Are Behind & Upgrade Opportunities

- Sidebar settings (pairs, params, risk) aren't persisted — a reload forgets
  them. localStorage, ~10 lines, large quality-of-life win.
- Pair checkboxes are `<div>`s with click handlers: not keyboard-accessible,
  not focusable, no ARIA. Same for nav items (`<a>` without `href`).
- Chart has no hover tooltips (values per trade) and no text alternative.
- No date-range control (paired with the Data Layer item).

### Action Plan

- [ ] Insert `${xLabels}` into the SVG template (or delete the dead builder and
      decide the chart has no x-axis on purpose)
- [ ] Remove the empty `opacity="0"` `<text>` placeholder
- [ ] Wrap startup fetches in try/catch and show a real error state
- [ ] Guard `renderTrades()` against a missing `exit_reason`
- [ ] Escape interpolated strings before they hit `innerHTML`
- [ ] Don't re-enable Run in `finally` when there are no strategies
- [ ] One visual pass over the exit panel at desktop width
- [ ] Persist sidebar settings to localStorage
- [ ] Keyboard/ARIA pass on pair list and nav
```

---

## Sector 6 — Backend API & Pipeline

**Issue title:**
`[System Cleanup & Upgrade] Backend API & Pipeline`

**Issue body:**

```markdown
### Everything Broken or Unneeded in This Sector

- 🟡 🆕 **Malformed input returns 500, not 400.** `int(req.get("max_hold_days", 10))`
  in `/api/backtest` raises `ValueError` on garbage input, which escapes as an
  unhandled 500. Engine-level validation errors are handled properly (caught →
  400); this one isn't. There's also no app-level error handler, so any
  unexpected exception returns a bare HTML 500 into code that expects JSON.
- 🟡 **`os.chdir(ROOT)` at import time** in `dashboard/app.py` is a global
  process side effect executed as a side effect of importing a module. It
  works, but it's the kind of thing that surprises the next reader — and it's
  a workaround for the cwd-relative paths in the Data Layer sector.
- 🟡 Server console noise from `summarize()` prints (see Analysis sector).
- 🟡 matplotlib imported for hex conversion only (see Data Layer sector).
- 🟢 No `/favicon.ico` route → one 404 per browser session. Cosmetic.

### Where We Are Behind & Upgrade Opportunities

- Flask's dev server is the **right** choice for a localhost tool (bound to
  127.0.0.1, debug off). If this is ever exposed beyond the machine it needs
  waitress/gunicorn and auth — recorded so that's a decision, not an accident.
- `/api/backtest` is synchronous. Cached ranges answer in ~50 ms, but a
  fresh-range Yahoo download can block for seconds with no progress feedback.
  Fine now; revisit when date-range controls land.
- Compare will need a saved-runs store. An in-memory dict is enough — runs are
  ~15 ms and deterministic, so it's a convenience cache, not a source of truth,
  and can be thrown away at any time.

### Action Plan

- [ ] Validate/coerce request fields properly; return 400 with a message
- [ ] Add a JSON error handler so the API never returns HTML to fetch()
- [ ] Remove `os.chdir` once paths are anchored (Data Layer)
- [ ] Quiet `summarize`; hex colours (tracked in their own sectors)
- [ ] Add a favicon route or inline data-URI
- [ ] Saved-runs store keyed by strategy+params (pending the key decision)
```

---

## Sector 7 — Journal

**Issue title:**
`[System Cleanup & Upgrade] Journal`

**Issue body:**

```markdown
> This whole sector is scheduled for scrap-and-rebuild in Issue #1. Listed
> here for completeness so the sweep is genuinely total.

### Everything Broken or Unneeded in This Sector

- 🔴 **`close_trade()` silently creates a phantom row.** In `core/journal.py`,
  `journal.loc[bad_index, "exit_price"] = value` uses pandas `.loc` enlargement:
  passing an index that doesn't exist **invents a new row** in what is meant to
  be the real-money record, with no error. Known since the first review; still
  live.
- 🔴 **`log_trade.py` logs a hardcoded example trade on every run** — running
  it twice duplicates the entry into the real journal.
- 🟡 **Unstable schema**: `exit_price` / `outcome_notes` columns only exist
  after the first `close_trade()`, so the CSV shape depends on history.
- 🟡 **`JOURNAL_PATH` is cwd-relative** — same class of bug as the Data Layer.
- 🟡 `journal/trade_journal.csv` holds one test entry; **user has approved
  deleting it**.
- 🟡 **Neither file has ever been modified since the initial commit** and
  neither has any test.

### Where We Are Behind & Upgrade Opportunities

Issue #1's split design supersedes all of the above: `/journal` package with
`backtest_journal.py`, `live_journal.py`, `broker_sync.py`, `storage.py`; one
shared schema; two separate stores. One addition from the Tracker plan
(`docs/notes.md`): **log the intended stop distance at entry** — `r_multiple`
cannot be reconstructed later, and the broker API will never tell you what
your stop was meant to be.

### Action Plan

- [ ] Implement Issue #1 as specced (package, two stores, one schema)
- [ ] Delete `core/journal.py`, `log_trade.py`, `journal/trade_journal.csv`
- [ ] Include `intended_stop_distance` in the shared schema
- [ ] Add tests — this is the module that touches real money
```

---

## Sector 8 — Root, Config & Repo Hygiene

**Issue title:**
`[System Cleanup & Upgrade] Root, Config & Repo Hygiene`

**Issue body:**

```markdown
### Everything Broken or Unneeded in This Sector

- 🔴 **Dead worktree** (RESOLVED during this sweep):
  `.claude/worktrees/friendly-shtern-f46823/` was a full duplicate of the
  project — 25 files including copies of all four data caches — left by a task
  session that produced **0 commits** against a clean tree. Verified
  contentless; the worktree and its branch have been removed. Nothing lost.
- 🟡 **No README.md.** The repo is public on GitHub with no explanation of what
  it is, how to run the dashboard, or how to add a strategy.
- 🟡 **No CI.** 27 tests exist and nothing runs them automatically. A GitHub
  Actions workflow (~15 lines, pytest on push) makes every future push
  self-checking — and once the engine verification suites are ported, CI
  becomes the engine's permanent guarantee rather than a promise.
- 🟡 **Duplicate commit in history**: "Add local data caching..." was committed
  twice (86d55aa, 44d9d74). Cosmetic; do not rewrite published history.
- 🟢 **`conftest.py` is empty and looks like junk but is load-bearing** — its
  presence is what puts the project root on `sys.path` for pytest. It needs a
  one-line comment saying so, or it will be "cleaned up" one day and take the
  whole suite down.
- 🟢 `__pycache__/` on disk: gitignored, regenerated, cosmetic only.
- 🟢 `.claude/launch.json` is committed on purpose (documents how the dashboard
  is launched). Not junk.

### Where We Are Behind & Upgrade Opportunities

- Dependencies are honest: 5 direct, all pinned, all actually imported
  (verified by scan). matplotlib becomes CLI-only once `pairs.py` stores hex —
  keep it, but it stops being a web-server dependency.
- Optional `pyproject.toml` to declare the Python floor (3.14 in use) and
  centralise tool config. No packaging need — this isn't a library.
- No LICENSE. Fine for a personal repo; add one only if it's meant to be
  genuinely open.

### Action Plan

- [x] Remove the dead worktree and its branch — done
- [ ] Write README.md (what/why, quickstart, dashboard, adding a strategy)
- [ ] Add `.github/workflows/tests.yml` running pytest on push
- [ ] Add the one-line comment to `conftest.py` explaining why it exists
```
