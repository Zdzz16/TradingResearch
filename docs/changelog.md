# Changelog

Short entries, newest first. One line per thing — no explanations.

## 2026-07-19
- Switched data source to Dukascopy (real prices, real spot gold)
- Fixed Dukascopy calendar-day bars (dropped Saturdays, folded Sunday into Monday)
- Built the Compare page (select vs select, transposed table, overlaid curves)
- Reorganised docs; added CLAUDE.md, changelog and auto-memory rules

## 2026-07-17
- Ran the landscape research; distilled it into the roadmap

## 2026-07-16
- Fixed six frontend bugs
- Added date range + in-sample/out-of-sample split to the Backtest page
- Bug-hunted analysis.py; removed spent script

## 2026-07-15
- Engine v4: exit signals, limit entries, position cap, ambiguity bounds, commission
- Scrapped Streamlit, built our own Flask dashboard
- Built the Backtest page (sidebar, stat cards, equity curve, trades, exit breakdown)
- Strategies became drop-in files in /strategies (auto-discovered)
- Rebuilt the journal (SQLite, backtest + live, one schema)
- Added the account simulator (equity, margin, refuses unaffordable trades)
- Proved no look-ahead bias; covered every untested engine feature
- Hardened the backend (paths, JSON errors, validation, date range, new endpoints)
- Ran the full system diagnosis; published GitHub issues #5–#12

## 2026-07-14
- First working version (data, strategy, engine, analysis, plotting, journal)
- Fixed the engine's entry-day and off-by-one bugs
- Stopped overlapping trades by default (163 → 127 trades)
- Added realistic gap fills
- Added the pair registry (4 instruments) and local data caching
- Added R-multiples, expectancy, max drawdown, ambiguity flag
- Engine v3: shorts, per-signal risk, trailing/break-even stops, swap, slippage
