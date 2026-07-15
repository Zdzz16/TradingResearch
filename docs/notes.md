# Notes

## 2026-07-15 — Data upgrade: Dukascopy (Swiss bank, free)

When we outgrow Yahoo, the upgrade path is (in order):

1. **Dukascopy** — Swiss bank, gives away **tick-level FX and spot gold (XAU/USD) history for free**, going back ~20 years. Biggest data-quality jump available at $0: real traded prices instead of Yahoo's indicative quotes (which have 30–82 incoherent bars per pair), true spot gold instead of the GC=F futures proxy, and intraday resolution that eliminates the engine's same-bar stop/target ambiguity instead of just flagging it. Needs a downloader tool (e.g. dukascopy-node) — integration point is `get_data()` in core/data_loader.py + the ticker in core/pairs.py.
2. **OANDA practice account (free)** — API candles with real bid/ask for exactly our four pairs → measured spreads instead of the estimated `spread_pips` in the registry.
3. **Paid, only when going live / systematically intraday** — Polygon.io (~$30–200/mo) or Databento (pay-as-you-go, gold futures ticks).

Engine note: it's already bar-size agnostic — feed it hourly bars and every
"day" parameter simply means "bar." No engine changes needed for intraday.
