"""
TradingResearch dashboard — our own web app (Flask).

No third-party UI framework and no chrome — every pixel is ours. This file
serves the page and exposes a small JSON API; templates/index.html plus
static/ do the presenting. All trading logic stays in core/ — the API only
calls run_strategy(), the same entry point the command line uses, so the
dashboard can never drift from the verified engine.

Run:  python3 dashboard/app.py      then open http://127.0.0.1:8501
"""

import os
import sys
from pathlib import Path

# dashboard/app.py -> the project root is one level up. Streamlit-free Flask
# only knows its own folder, so add the root to the import path; and make it
# the working directory so the pipeline's relative paths (data_cache/,
# results/) resolve no matter where the app was launched from.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import matplotlib.colors as mcolors
import pandas as pd
from flask import Flask, jsonify, render_template, request

from core.analysis import summarize
from core.pairs import PAIRS, DEFAULT_SL_PIPS, DEFAULT_TP_PIPS
from run_backtest import run_strategy

app = Flask(__name__)
# Pick up edits to templates/ and static/ on the next browser refresh, so
# iterating on the UI doesn't need a server restart.
app.jinja_env.auto_reload = True
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

# Columns the trades list actually shows — everything else the engine
# records stays out of the UI to keep it readable.
TRADE_COLUMNS = ["entry_date", "exit_date", "direction", "entry_price",
                 "exit_price", "exit_reason", "profit", "r_multiple", "days_held"]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/pairs")
def api_pairs():
    """The pair registry — so the UI builds its controls from the same
    single source of truth the engine uses, instead of a hardcoded copy."""
    return jsonify([
        {
            "name": name,
            "color": mcolors.to_hex(cfg["color"]),
            "sl_pips": cfg.get("sl_pips", DEFAULT_SL_PIPS),
            "tp_pips": cfg.get("tp_pips", DEFAULT_TP_PIPS),
        }
        for name, cfg in PAIRS.items()
    ])


@app.route("/api/backtest", methods=["POST"])
def api_backtest():
    """Runs the backtest for the selected pairs and returns everything the
    page needs: one equity series per pair, a pooled trade list, and the
    combined stats."""
    req = request.get_json(force=True) or {}
    names = [n for n in req.get("pairs", []) if n in PAIRS]
    if not names:
        return jsonify({"error": "Pick at least one pair."}), 400

    window = int(req.get("window", 20))
    max_hold = int(req.get("max_hold_days", 10))
    # None = let each pair use its own defaults from the registry.
    sl_pips = req.get("sl_pips")
    tp_pips = req.get("tp_pips")

    series, frames = [], []
    for name in names:
        try:
            trades, _ = run_strategy(
                name, sl_pips=sl_pips, tp_pips=tp_pips,
                window=window, max_hold_days=max_hold, save_csv=False,
            )
        except Exception as exc:  # bad ticker, no data, bad params
            return jsonify({"error": f"{name}: {exc}"}), 400

        equity = trades["r_multiple"].cumsum().tolist() if len(trades) else []
        series.append({
            "pair": name,
            "color": mcolors.to_hex(PAIRS[name]["color"]),
            "points": equity,
        })
        if len(trades):
            tagged = trades.copy()
            tagged["pair"] = name
            frames.append(tagged)

    if not frames:
        return jsonify({"error": "These settings produced no trades."}), 400

    # Pool every selected pair's trades in date order: that's the portfolio
    # view — what an account trading all of them at once would have seen.
    pooled = pd.concat(frames).sort_values("entry_date").reset_index(drop=True)
    combined = summarize(pooled, label="Combined")
    combined["exit_reasons"] = pooled["exit_reason"].value_counts().to_dict()

    table = pooled[[c for c in TRADE_COLUMNS if c in pooled.columns] + ["pair"]].copy()
    for col in ("entry_date", "exit_date"):
        table[col] = pd.to_datetime(table[col]).dt.strftime("%Y-%m-%d")
    # NaN is not valid JSON — send nulls instead.
    table = table.astype(object).where(pd.notna(table), None)

    return jsonify({
        "series": series,
        "combined": combined,
        "trades": table.to_dict(orient="records"),
    })


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8501, debug=False)
