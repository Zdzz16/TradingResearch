# Research Notes — Landscape Survey Distilled

One note per idea from the landscape research, in a fixed shape:

- **What** — a one-liner on the thing.
- **Benefit** — how it could help *us* specifically.
- **Worth knowing** — caveats, tools, effort, anything load-bearing.
- **My take** — my own read (marked so you know what's me vs the research).

**Tags:** `Feature` (new capability) · `Upgrade` (improve something we have) ·
`Direction` (a trend/strategy/awareness item, not a concrete build) ·
`Have ✓` (we already do this — flagged because the report calls several of
them "advanced").

> **Headline before the notes:** a surprising number of the report's
> "maturity signals" are already in our codebase — event-driven engine,
> look-ahead avoidance (proven), shared-margin multi-asset account, gap-aware
> stop fills, swap/financing cost, MAE/MFE recorded per trade, IS/OOS split in
> the UI, and a unified backtest+live journal. We're further along the
> "serious tool" axis than a typical solo project. The biggest gaps are in
> *validation rigor*, *surfacing live setups*, and *reviewing trades*, not in
> the engine.

---

## A. Backtesting & Analysis Engine

### A1. Event-driven, bar-by-bar architecture — `Have ✓`
- **What:** Walk the data bar-by-bar, re-evaluating order state each step, instead of vectorized array math over the whole history.
- **Benefit:** It's the "realistic execution" camp — faithful order state, no accidental look-ahead. The report puts this above vectorized engines for fidelity.
- **Worth knowing:** The trade-off is speed; the mature pattern is to *use both* — vectorized for fast idea triage, event-driven to validate.
- **My take:** We're already on the right side of the field's central dividing line. Our whole `run_backtest` is this. No action needed — just know it's a strength.

### A2. Vectorized triage layer (e.g. vectorbt-style) — `Direction`
- **What:** A fast, array-based pass that can test thousands of parameter combos in seconds.
- **Benefit:** "Does this even have an edge?" screening before spending time on a realistic run.
- **Worth knowing:** vectorbt / vectorbt PRO is the reference. Structurally weak on fills, so it's a *screen*, not a verdict.
- **My take:** Low priority for us — our engine runs 4 pairs × 10 years in ~46ms, so speed isn't our bottleneck yet. Only matters once we do big parameter sweeps. File under "if we ever grid-search hard."

### A3. Portfolio-level, shared-margin, multi-asset backtest — `Have ✓ (partial)`
- **What:** One cash/margin account shared across all instruments, so positions compete for capital.
- **Benefit:** This is the single feature the report says separates "strategy testers" from "portfolio engines."
- **Worth knowing:** LEAN and NautilusTrader are the exemplars.
- **My take:** We built exactly this in `core/account.py` — a EURUSD position eats margin the gold trade then can't have, and it refuses trades on insufficient margin. It's not wired into the dashboard yet (that's the `/api/account` endpoint waiting for a UI). We have the hard part; we're missing the screen.

### A4. Portfolio-construction models (mean-variance, risk parity, Black-Litterman) — `Direction`
- **What:** Pluggable allocation models that decide how much weight each instrument gets.
- **Benefit:** Turns "which pairs" into a principled sizing decision instead of equal-weight.
- **Worth knowing:** A LEAN signature feature; genuinely institutional.
- **My take:** Overkill for 4 forex pairs. Our fixed-fractional risk-per-trade sizing is the right altitude. Park it.

### A5. Standard metric vocabulary (Sharpe, Sortino, Calmar, Omega, profit factor, VaR/CVaR, Ulcer, recovery factor) — `Upgrade`
- **What:** The ratio family that is the shared "reporting language" of the whole space.
- **Benefit:** Lets us compare our results to how everyone else describes theirs; some (profit factor, Sortino) are genuinely more informative than raw win rate.
- **Worth knowing:** Our expectancy-in-R and break-even-win-rate are a trader-facing dialect of the same ideas — not wrong, just not the lingua franca.
- **My take:** Add **profit factor** and **max-drawdown duration** first (cheap, high signal). Sharpe/Sortino need a return series with a time axis, which is a bit more plumbing. Worth doing, medium effort.

### A6. QuantStats (drop-in analytics + tear-sheets) — `Feature`
- **What:** A library that computes 50+ metrics and generates an HTML/PDF tear-sheet in one line, and now ships a built-in Monte Carlo.
- **Benefit:** We'd get the entire metric family + a shareable report almost for free, instead of hand-rolling each stat.
- **Worth knowing:** It expects a returns series (pandas). Would be a new dependency — mild tension with our "lean deps" stance.
- **My take:** Tempting, but it wants returns-over-time and we think in per-trade R. A one-off adapter (trades → daily returns) unlocks it. Could be a big analytics jump for small effort *if* the adapter is clean. Worth a spike.

### A7. Parameter optimization framework (grid / random / Bayesian / genetic, via Optuna) — `Feature`
- **What:** Systematic search over strategy parameters instead of manual guessing.
- **Benefit:** Finds good settings faster; Optuna unifies the methods behind one API and shows up in many indie repos.
- **Worth knowing:** **Random search often beats grid** at limited budget and is far faster. Grid search *actively promotes overfitting* — the report is emphatic that optimizer choice must be judged on out-of-sample quality, not in-sample Sharpe.
- **My take:** Do NOT build this before the validation tools in section B — an optimizer without overfitting defenses is a foot-gun that will hand us a beautiful, fake strategy. Optimizer + walk-forward are two halves of one feature.

---

## B. Validation & Robustness  *(our biggest real gap)*

### B1. Walk-forward analysis / optimization (WFA/WFO) — `Upgrade`
- **What:** Roll through history: optimize on an in-sample window, test on the next out-of-sample window, slide forward, stitch the OOS pieces into one equity curve.
- **Benefit:** The report calls it the "gold standard" — it simulates "performance if periodically recalibrated," which is what real trading is.
- **Worth knowing:** Built natively into NinjaTrader/MultiCharts/AmiBroker; in Python it's assembled manually. Limits: window-size choice adds bias, it's computationally heavy, and it reacts to regime shifts rather than predicting them.
- **My take:** This is the natural next step *up* from the IS/OOS split we already have — same idea, done repeatedly and rolling. Highest-value validation upgrade. Our date-range API already supports arbitrary windows, so the backend is half-ready.

### B2. Monte Carlo — trade-order resampling — `Feature`
- **What:** Shuffle/bootstrap the sequence of trade results thousands of times to get a *distribution* of outcomes (drawdowns, final equity, risk-of-ruin) instead of one path.
- **Benefit:** Answers "how bad could the drawdown have been?" and "what's my risk of ruin?" — the single history we have is just one lucky/unlucky ordering.
- **Worth knowing:** QuantStats ships this; NinjaTrader and TradeZella have it too. Cheap to implement — we already have the trade list.
- **My take:** **High value, low effort, do it early.** We have `r_multiple` per trade already; a few dozen lines resamples them. This is the most bang-for-buck item in the whole report for building trust. Pairs beautifully with the account layer (dollar risk-of-ruin).

### B3. Combinatorial Purged Cross-Validation (CPCV) — `Direction`
- **What:** López de Prado's method — many train/test combinations with "purging" and "embargoing" to prevent time-leakage.
- **Benefit:** Recent research finds it *beats* walk-forward at detecting overfitting.
- **Worth knowing:** Active research frontier; almost never in retail tools; the "beats walk-forward" claim is from a synthetic study, not settled consensus.
- **My take:** Too advanced for where we are. Note it exists; revisit only if we get serious about a real edge. Walk-forward first.

### B4. Synthetic price-path Monte Carlo — `Direction`
- **What:** Generate many fake-but-realistic price series, run the strategy, and see how the Sharpe distributes; in-sample result showing as an outlier = overfitting signature.
- **Benefit:** A different, powerful overfitting check than trade-shuffling.
- **Worth knowing:** Rare; some use GANs. Meaningfully harder than B2.
- **My take:** Cool, not now. B2 gives 80% of the confidence for 10% of the work.

### B5. Deflated Sharpe / PBO / multiple-testing correction — `Direction`
- **What:** Statistics that *deflate* a reported result for the fact that you tried many configurations and reported the winner.
- **Benefit:** The honest antidote to "I tested 50 settings and this one looked great." A strong maturity signal — almost only in academia/institutions.
- **Worth knowing:** Deflated Sharpe Ratio (Bailey & López de Prado), Probability of Backtest Overfitting.
- **My take:** The concept matters more than the implementation right now: **every parameter we try makes our best result look better than it is.** Even without coding DSR, we should track how many configs we've tried and stay suspicious. A "trials counter" would be a cheap, honest nod to this.

### B6. "Overfit strategies systematically *under*-perform" — `Direction (know-this)`
- **What:** Because of memory effects in price series, an overfit strategy doesn't just fail to beat OOS — it tends to actively lose.
- **Benefit:** Reframes overfitting from "no edge" to "negative edge" — raises the stakes of validation.
- **My take:** Worth internalizing given our edge is already thin. The downside of fooling ourselves isn't break-even, it's losses.

---

## C. Data & Execution Realism

### C1. Dukascopy free tick/candle data — `Feature`
- **What:** Free tick-by-tick forex (and gold) from Dukascopy's ECN pool, tick→monthly, CSV.
- **Benefit:** Real traded prices vs Yahoo's indicative quotes; real spot gold instead of the GC=F proxy; enables intraday.
- **Worth knowing:** Python helpers exist (`tickterial` caches ticks locally; `dukascopy-node` — we have Node). Tickstory pulls Dukascopy into MT4/5 for "99% modeling quality."
- **My take:** Already our planned #1 data move. The report confirms it's the most-respected *free* source. Daily first (apples-to-apples vs Yahoo), then intraday.

### C2. Other free data sources (HistData, TrueFX, Alpha Vantage, Twelve Data, Finnhub) — `Feature`
- **What:** A spread of free feeds — HistData (66 pairs, MT-formatted), TrueFX (tick w/ fractional-pip spreads + ms timestamps), and yfinance-replacement APIs.
- **Benefit:** Options if Dukascopy is awkward, or cross-checking data quality between sources.
- **Worth knowing:** The API ones have rate limits and mostly EOD/delayed on free tiers.
- **My take:** TrueFX is interesting — it includes *spreads*, which we currently estimate. Good for validating our spread assumptions. Secondary to Dukascopy.

### C3. yfinance is a scrape, not an API — `Direction (know-this)`
- **What:** Every guide warns yfinance is web-scraping Yahoo — rate limits, schema drift, no commercial footing.
- **Benefit:** Explains our own `droplevel`/empty-data guards; tells us not to build anything load-bearing on it.
- **My take:** We already hit its schema quirks (the MultiIndex flatten). Fine for learning/prototyping; the move to Dukascopy is also a move off a fragile foundation.

### C4. Slippage models — fixed vs square-root market impact — `Upgrade`
- **What:** Slippage from a simple fixed pip offset (our current model) up to a √(order size / ADV) market-impact model, decomposed into *delay slippage* and *market impact*.
- **Benefit:** More honest fills, especially as size grows.
- **Worth knowing:** Also: our slippage only applies to stop exits, not entries — a known gap.
- **My take:** Market-impact modeling is irrelevant at retail size (we don't move the market). But **entry slippage** is the real missing piece and it's already on our list for the engine session. Fixed-pip is fine; we just need to apply it to entries too.

### C5. Stop-loss fill realism ("slippage through stops") — `Have ✓`
- **What:** Real stops become market orders and fill *worse* in fast markets; naive backtests fill exactly at the stop.
- **Benefit:** The report flags this as a specific trap that turns a "2% loss" into a 5% loss.
- **My take:** Our gap-aware fills already handle exactly this — if price gaps through the stop, we fill at the open, not the stop level. We're ahead of the naive default here.

### C6. Broker practice-account data (OANDA) — `Feature`
- **What:** Real bid/ask from a broker's API, free with a (practice) account.
- **Benefit:** Measured spreads instead of our registry estimates, and it's the same connection we'd use for the live journal + execution.
- **My take:** OANDA keeps recurring — data + execution + forex-native in one place. Strong candidate for the eventual live side. Practice account is free.

### C7. Survivorship bias is (mostly) not our problem — `Direction (know-this)`
- **What:** Testing only on instruments that still exist inflates returns — a big deal for equities/indices.
- **Benefit:** Reassurance: the FX majors don't get delisted, so this bias barely touches us.
- **My take:** Nice — one whole class of "serious backtesting" worry we get to skip by trading majors. Worth remembering if we ever add exotic pairs or stocks.

### C8. "Only live trading is truly out-of-sample" — `Direction (know-this)`
- **What:** Merely having lived through the test period leaks insight; backtests have look-ahead "by design."
- **My take:** Humbling and correct. Argues for getting to *paper/live* sooner rather than polishing the backtest forever — which lines up with your goal of trading again.

---

## D. Live Trading, Alerts & "Seeing Setups"  *(your stated goal)*

### D1. TradingView alerts → webhook → destination — `Direction`
- **What:** The dominant retail pattern: a Pine/indicator alert fires on a condition and routes to SMS/email or a webhook URL.
- **Benefit:** This *is* the "see setups on TradingView + get notified" workflow you described, and it's the most-trodden path in the whole space.
- **Worth knowing:** `alert.freq_once_per_bar_close` avoids repainting (fire on the confirmed bar, not intra-bar). TradingView caps alerts per plan tier.
- **My take:** The realistic shape of "trade again" for you: our strategy as a TradingView indicator, alerts on setup, a relay to your phone. Doesn't require our platform to be live at all — TradingView does the watching.

### D2. Notification relay (webhook → Telegram / Discord / ntfy / Pushover) — `Feature`
- **What:** A tiny Flask listener that receives a webhook and fans it out to chat/push targets, with templated messages and a shared secret.
- **Benefit:** Alerts land on your phone. Off-the-shelf open-source relays exist (fabston/TradingView-Webhook-Bot, MasDenk/TradingViewTelegram).
- **Worth knowing:** Usually run on a cheap VPS; Discord/Telegram have their own rate limits.
- **My take:** We could literally reuse our existing Flask app as the listener — it's the same stack. This is a small, satisfying, *directly-serves-the-goal* build. ntfy/Pushover are the simplest for pure phone push.

### D3. Our own Python "watcher" (poll data → push) — `Feature`
- **What:** Instead of TradingView, our own scheduled job pulls data, runs the strategy's signal logic, and pushes on a setup.
- **Benefit:** Same signal code as the backtest = guaranteed parity with what we tested; no TradingView plan limits.
- **Worth knowing:** We own the uptime/hosting; TradingView owns the charts.
- **My take:** The compelling version long-term, because it closes the "what I see = what I backtested" gap by construction. But it means *we* host the watcher. TradingView (D1) is the faster path to "notified this week."

### D4. Execution bridges (TradersPost etc.) — `Feature`
- **What:** Services that turn a TradingView webhook into a real broker order.
- **Benefit:** The no-code "signal → order" layer for semi-auto trading.
- **My take:** Only relevant once you want the *confirm-and-place* step automated. For "see setup, place manually," skip it. Good to know it exists for later.

### D5. Broker APIs for automation (Alpaca / IBKR / OANDA / CCXT) — `Feature`
- **What:** Direct programmatic order placement. OANDA is the forex-relevant one (streaming prices + REST orders + reconciliation).
- **Benefit:** The foundation for both live data and eventual execution + auto-journaling.
- **Worth knowing:** Alpaca is the developer darling but US-stocks-only (no forex). CCXT is crypto.
- **My take:** For us it's OANDA or bust on the forex side. Our `journal/broker_sync.py` placeholder was written with exactly this in mind.

### D6. Paper trading before live is "non-negotiable" — `Direction (know-this)`
- **What:** Every serious source insists on API paper-trading (sandboxes at ~98–99% fidelity) before real money.
- **Benefit:** It's where the live journal earns its keep — the paper stage generates your first "live" records to compare against the backtest.
- **My take:** Our split backtest/live journal is purpose-built for this. Paper-trade via OANDA practice, log to the live table, compare to the backtest. That loop is the real prize.

### D7. Research-to-live code parity — `Direction`
- **What:** The same strategy object runs in backtest and live, so nothing is re-implemented (and can't drift) — NautilusTrader/LEAN's headline promise.
- **Benefit:** Eliminates the "the live version behaves differently" class of bug.
- **My take:** We already have a mild version of this discipline (the dashboard calls the same `run_strategy` the CLI does). If we build the watcher (D3) on our own signal code, we get parity for free. It's a principle to protect, not a feature to buy.

---

## E. Dashboard & UX

### E1. Price chart with trade entry/exit markers — `Upgrade`
- **What:** Plot the actual candlesticks with each trade's entry/exit marked, not just an equity line.
- **Benefit:** The report calls chart-linked trade inspection "the strongest debugging affordance" — you *see* why a trade happened.
- **My take:** Our dashboard shows an equity curve and a trades table but no price chart. This is the biggest UX gap for "seeing setups" inside our own tool. Medium effort with our hand-drawn SVG approach; this is where a charting lib (E4) tempts.

### E2. Click-a-trade → see it in context — `Upgrade`
- **What:** Select a trade in the table and jump to that moment on the price chart.
- **Benefit:** Turns the trades table from a log into an investigation tool.
- **My take:** Natural follow-on to E1. Together they'd make the Backtest page genuinely inspectable.

### E3. Run comparison / session history — `Feature`
- **What:** Store multiple backtests and view them side by side.
- **Benefit:** This is literally our planned **Compare page**, and the report confirms it's a defining "good UI" feature (VolForge, TradeZella have it).
- **My take:** Backend's already done — `/api/runs` stores runs keyed by strategy+params. Just needs the UI. Directly on our roadmap.

### E4. Professional candlestick rendering (TradingView Lightweight Charts) — `Direction`
- **What:** A free, high-quality charting library for candlesticks with markers.
- **Benefit:** Would make E1/E2 look pro without hand-drawing everything.
- **Worth knowing:** It's a dependency + CDN/bundle — tension with our deliberate "dependency-free, hand-drawn SVG" choice.
- **My take:** Real fork in the road: keep everything hand-built (more control, more work) or adopt Lightweight Charts for price views (fast, polished, one dependency). I lean toward adopting it *only* for the price/candlestick view, where hand-drawing is genuinely hard, and keeping our SVG for equity curves. Worth a conscious decision, not a drift.

### E5. Static → interactive charts (hover / zoom / pan) — `Direction`
- **What:** The field is moving away from static report images toward explorable dashboards.
- **Benefit:** Explore any trade/metric instead of squinting at a fixed chart.
- **My take:** Our SVG is static-ish. Tooltips on the equity curve are a cheap first step (was already flagged as a nice-to-have). Full pan/zoom is more work; do it if/when we adopt a charting lib.

### E6. Full front-end control (hand-built Flask/JS) — `Have ✓`
- **What:** We built our own front end instead of defaulting to Streamlit like most indie projects.
- **Benefit:** The report notes this is *unusual* for a solo project and a real differentiator in UX control.
- **My take:** Validates the Streamlit-scrap decision from way back. It cost more work; we own every pixel and there's no framework chrome. Keep it.

---

## F. Journal & Trade Review  *(a mature commercial category we can raid for ideas)*

### F1. Unified backtest + live journal in one store — `Have ✓`
- **What:** Backtest results and real trades in the same schema/store.
- **Benefit:** The report explicitly says commercial journals are *almost all live-only* and "don't connect backtest results to a journal at all" — you track that comparison manually. A unified store is **uncommon in the space**.
- **My take:** This is a genuine structural advantage we already built (`journal/` — shared schema, two tables). The whole point is "did live match the backtest?" and we're set up to answer it when almost no one else is.

### F2. Broker auto-import into the journal — `Feature`
- **What:** Pull entry/exit/size/fees/timestamps automatically from the broker instead of typing them.
- **Benefit:** The single most-emphasized journal feature — "if logging a trade takes more than 30 seconds, you'll stop." Leaders integrate 500–700+ brokers.
- **My take:** For us this is the OANDA API → `live_journal` path (our `broker_sync.py` placeholder). We don't need 700 brokers — we need *one*. High value once trading.

### F3. MFE / MAE analysis — `Have ✓ (data) / Upgrade (display)`
- **What:** Maximum Favorable / Adverse Excursion — how far a trade went for/against you before exit. Near-universal among journal leaders.
- **Benefit:** Reveals whether stops are too tight (winners' MAE hugs the stop) or targets too close (MFE runs way past the target). Directly tunes our exit rules.
- **My take:** **The engine already records `mae` and `mfe` per trade** — we just don't display or analyze them anywhere. This is low-hanging fruit: the expensive part (computing them correctly on full bars) is done; we only need to surface them. Do this.

### F4. Best-exit / optimal-exit analysis — `Feature`
- **What:** Model where you *could* have exited vs where you did.
- **Benefit:** Quantifies money left on the table; points at better exit logic.
- **My take:** A natural extension of having MAE/MFE. Medium effort. Good "make the strategy better without changing entries" tool.

### F5. "What-if" exit testing on real entries (Edgewonk's Trade Management Optimizer) — `Feature`
- **What:** Take your *actual historical entries* and replay different exit rules against them.
- **Benefit:** Separates "is my entry good?" from "is my exit good?" — you can fix exits without touching entries.
- **My take:** Genuinely clever and the report calls it "unique." Our engine already parameterizes exits (SL/TP/trailing/BE/time), so we could re-run held entries under different exit configs. Fits our architecture unusually well.

### F6. Performance simulator (tweak win rate / avg win / avg loss) — `Feature`
- **What:** A calculator: "if my win rate were 45% instead of 40%, what happens?"
- **Benefit:** Builds intuition for which lever matters most for *our* numbers.
- **My take:** Tiny to build, surprisingly motivating. Could live on the dashboard as a little sandbox. Low effort, nice-to-have.

### F7. Tag-based setup analysis — `Feature`
- **What:** Tag each trade by setup type (breakout, pullback, reversal) and see which setups actually make money.
- **Benefit:** "see the setups" in the analytical sense — which patterns pay vs which just feel good.
- **My take:** Our journal schema has a `notes`/`reason` field; a structured `tag` column + a per-tag stats view would deliver this. Ties to your interest in *seeing* setups. Medium effort.

### F8. Trade replay (bar-by-bar) — `Feature`
- **What:** Step through a historical trade bar by bar to study it.
- **Benefit:** Deep review; journal leaders offer it at increasing fidelity.
- **My take:** Nice, but needs the price-chart view (E1) first. Sequence it after E1/E2.

### F9. AI journaling layers (auto-tagging, session review, coaching) — `Direction`
- **What:** LLM features on top of the journal — auto-tag trades, weekly review emails, "coaching."
- **Benefit:** The newest commercial frontier (Zella AI, Cypher AI, etc.).
- **My take:** Skip for now; it's polish on top of a journal we haven't fully built. Revisit once F1–F3 exist and there's data worth summarizing.

### F10. Prop-firm sync (FTMO/Topstep/Apex) — `Direction`
- **My take:** Not relevant unless you go the prop-firm route. Noting it exists; no action.

---

## G. Cross-Cutting Trends & Directions

### G1. Data cost dominates platform cost — `Direction (know-this)`
- **What:** For systematic traders, clean tick/minute data ($50–300/mo) dwarfs platform fees.
- **My take:** Argues for milking free Dukascopy hard before paying for anything. Our whole stack is free; the first dollar we spend should probably be data, and only if free data proves limiting.

### G2. Optimizer choice must be judged on OOS, not in-sample — `Direction (know-this)`
- **What:** Grid search actively promotes overfitting; speed/in-sample Sharpe are the wrong yardsticks.
- **My take:** The rule that binds section A7 to section B — never ship an optimizer without walk-forward/Monte-Carlo judging its output. Design them together.

### G3. LLM as *supporting* tool, not signal generator — `Direction`
- **What:** Naive LLM trading strategies underperform simple MA-crossover/momentum baselines and mostly lose after fees. LLMs *do* help with sentiment, idea generation, code generation, and research assistance.
- **Benefit:** Saves us from a fashionable dead end.
- **My take:** Reassuring that our humble MA baseline literally beats naive LLM strategies in the studies. If we use AI here, it's as a coding/research aid (like this), not as the trader. Also: "a Sharpe of 4.0 is more often leakage than genius" — a good sanity alarm.

### G4. No-code strategy builders — `Direction`
- **What:** Drag-and-drop strategy construction (StrategyQuant, Lune, etc.); "2026 is when algo goes mainstream."
- **My take:** Not our path — you can code and want control. Interesting as market context, not a feature to copy.

### G5. Automated strategy *generation* (StrategyQuant X) — `Direction`
- **What:** ML that machine-generates strategies and exports to MT4/5.
- **My take:** Explicitly out of scope (you're handling strategies separately), and it's an overfitting minefield. Awareness only.

### G6. Maintained ecosystem / community as a feature — `Direction (know-this)`
- **What:** The report keeps flagging *maintenance* — Backtrader is "effectively end-of-life," bugs nobody will fix.
- **My take:** A reminder that our own tests + clean structure are what keep *our* project from rotting. The 119-test suite is our version of "maintained." Worth protecting as we add features.

### G7. Our standing differentiators — `Have ✓ (synthesis)`
- **What:** The report explicitly lists three things indie projects *can* have that commercial tools often lack — and we have all three: (1) unified backtest+live journal, (2) full front-end control, (3) forex-appropriate cost modeling incl. swap/overnight financing.
- **My take:** Good to see our earlier decisions validated as genuine edges, not just effort. When prioritizing, we should *protect* these, not accidentally trade them away for convenience.

---

## Quick priority read (my synthesis, not from the report)

If we sort every note by (helps-the-goal ÷ effort), the standouts:

1. **Monte Carlo trade resampling (B2)** — trust, cheap, we have the data.
2. **Surface MAE/MFE (F3)** — already computed, just display it.
3. **Notification relay to your phone (D2)** — directly "get notified of setups," reuses our Flask stack.
4. **Walk-forward (B1)** — the real validation upgrade; backend half-ready.
5. **Compare page UI (E3)** — backend done, just needs the screen.
6. **Price chart with trade markers (E1/E2)** — "see setups" inside our tool.
7. **TradingView indicator + alerts (D1)** — fastest path to trading again, offloads the watching.

Everything else is either already done, genuinely advanced/deferred, or out of scope. The theme: our *engine* is ahead of our *validation* and our *trade-review/alerting* — so the highest-leverage work is proving trust and surfacing setups, not more engine.
