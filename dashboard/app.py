"""
TradingResearch dashboard — our own web app (Flask).

No third-party UI framework and no chrome — every pixel is ours. This file
serves the page and exposes the JSON API; templates/index.html plus static/
do the presenting.

All trading logic stays in core/ and journal/. This layer only validates
input, calls those modules, and shapes the answer as JSON. Nothing here
computes a price, a statistic or a position size — so the dashboard cannot
drift away from the code the tests actually cover.

Run:  python3 dashboard/app.py      then open http://127.0.0.1:8501
"""

import sys
from pathlib import Path

# dashboard/app.py -> the project root is one level up. Flask only knows its
# own folder, so put the root on the import path. (We used to os.chdir here
# as well; every module now anchors its own paths, so that hack is gone.)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
from flask import Flask, Response, jsonify, render_template, request

from core.account import simulate
from core.analysis import summarize
from core.pairs import PAIRS, DEFAULT_SL_PIPS, DEFAULT_TP_PIPS
from core.strategies import load_strategies, load_errors
from journal import backtest_journal, live_journal
from run_backtest import run_strategy, START, END

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

# Saved backtest runs, for the Compare page. Keyed by strategy + params, NOT
# by strategy alone: keyed by name, MA20 and MA50 would overwrite each other,
# and comparing a strategy against its own tuning is the cheap way to spot an
# overfitted parameter. Re-running the identical thing still replaces its own
# slot, so a run can never appear twice.
# In memory on purpose — a run takes ~15 ms and is deterministic, so this is
# a convenience cache, not a source of truth. Losing it costs nothing.
SAVED_RUNS = {}


# ----------------------------------------------------------------------
# Errors — the API must never hand HTML to code that asked for JSON
# ----------------------------------------------------------------------

class ApiError(Exception):
    """A problem worth telling the user about, with the right status."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


@app.errorhandler(ApiError)
def handle_api_error(err):
    return jsonify({"error": err.message}), err.status


@app.errorhandler(404)
def handle_404(err):
    if request.path.startswith("/api/"):
        return jsonify({"error": f"No such endpoint: {request.path}"}), 404
    return err


@app.errorhandler(Exception)
def handle_unexpected(err):
    """Anything we didn't foresee. Without this, Flask returns an HTML error
    page, fetch() tries to parse it as JSON, and the browser reports a
    JSON.parse failure — which tells you nothing about what actually broke."""
    app.logger.exception("Unhandled error on %s", request.path)
    if request.path.startswith("/api/"):
        return jsonify({"error": f"{type(err).__name__}: {err}"}), 500
    raise err


# ----------------------------------------------------------------------
# Input validation — every value from the browser is untrusted
# ----------------------------------------------------------------------

def _body():
    try:
        data = request.get_json(force=True, silent=False)
    except Exception:
        raise ApiError("Request body is not valid JSON.")
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ApiError("Request body must be a JSON object.")
    return data


def _number(body, key, default=None, minimum=None, maximum=None, required=False):
    """Reads a number, or explains precisely what was wrong with it.

    Without this, int(body["max_hold_days"]) on garbage raised a bare
    ValueError that escaped as a 500 — the server implying its own fault
    when the request was simply malformed.
    """
    if key not in body or body[key] is None:
        if required:
            raise ApiError(f"'{key}' is required.")
        return default
    value = body[key]
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ApiError(f"'{key}' must be a number, got {type(value).__name__}.")
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ApiError(f"'{key}' must be a number, got {body[key]!r}.")
    if value != value or value in (float("inf"), float("-inf")):
        raise ApiError(f"'{key}' must be a finite number.")
    if minimum is not None and value < minimum:
        raise ApiError(f"'{key}' must be at least {minimum}, got {value:g}.")
    if maximum is not None and value > maximum:
        raise ApiError(f"'{key}' must be at most {maximum}, got {value:g}.")
    return value


def _date(body, key, default):
    """Dates arrive as 'YYYY-MM-DD' strings and must be real dates."""
    value = body.get(key) or default
    try:
        return pd.Timestamp(value).strftime("%Y-%m-%d")
    except Exception:
        raise ApiError(f"'{key}' must be a date like 2015-01-01, got {value!r}.")


def _pairs(body):
    names = body.get("pairs")
    if not isinstance(names, list) or not names:
        raise ApiError("Pick at least one pair.")
    unknown = [n for n in names if n not in PAIRS]
    if unknown:
        raise ApiError(f"Unknown pair(s): {', '.join(map(str, unknown))}. "
                       f"Available: {', '.join(PAIRS)}")
    return names


def _backtest_settings(body):
    """One place that reads a backtest request, so /api/backtest and
    /api/account can never interpret the same body differently."""
    start = _date(body, "start", START)
    end = _date(body, "end", END)
    if start >= end:
        raise ApiError(f"'start' ({start}) must be before 'end' ({end}).")

    # Both absent = let every pair use its own defaults from the registry.
    use_defaults = body.get("sl_pips") is None and body.get("tp_pips") is None
    return {
        "pairs": _pairs(body),
        "strategy": body.get("strategy") or "ma_crossover",
        "params": body.get("params") or {},
        "max_hold_days": int(_number(body, "max_hold_days", 10, minimum=1, maximum=365)),
        "sl_pips": None if use_defaults else _number(body, "sl_pips", DEFAULT_SL_PIPS,
                                                     minimum=0.1, maximum=100_000),
        "tp_pips": None if use_defaults else _number(body, "tp_pips", DEFAULT_TP_PIPS,
                                                     minimum=0.1, maximum=100_000),
        "start": start,
        "end": end,
    }


def _run(settings):
    """Runs the selected pairs and returns (series, pooled trades).
    Strategy and data problems become 400s — they're bad input, not crashes."""
    series, frames = [], []
    for name in settings["pairs"]:
        try:
            trades, _ = run_strategy(
                name, sl_pips=settings["sl_pips"], tp_pips=settings["tp_pips"],
                strategy=settings["strategy"], params=settings["params"],
                max_hold_days=settings["max_hold_days"],
                start=settings["start"], end=settings["end"], save_csv=False,
            )
        except ValueError as exc:      # unknown strategy, bad param, no data
            raise ApiError(f"{name}: {exc}")
        except Exception as exc:       # network, corrupt cache, anything else
            raise ApiError(f"{name}: {type(exc).__name__}: {exc}", status=502)

        series.append({
            "pair": name,
            "color": PAIRS[name]["color"],
            "points": trades["r_multiple"].cumsum().tolist() if len(trades) else [],
        })
        if len(trades):
            tagged = trades.copy()
            tagged["pair"] = name
            frames.append(tagged)

    if not frames:
        raise ApiError("These settings produced no trades.")
    pooled = pd.concat(frames).sort_values("entry_date").reset_index(drop=True)
    return series, pooled


def _trade_table(pooled):
    table = pooled[[c for c in TRADE_COLUMNS if c in pooled.columns] + ["pair"]].copy()
    for col in ("entry_date", "exit_date"):
        table[col] = pd.to_datetime(table[col]).dt.strftime("%Y-%m-%d")
    # NaN is not valid JSON — send nulls instead.
    return table.astype(object).where(pd.notna(table), None).to_dict(orient="records")


# ----------------------------------------------------------------------
# Pages
# ----------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/favicon.ico")
def favicon():
    """Answer the browser's automatic request instead of logging a 404 every
    session. Inline SVG keeps it to zero extra files."""
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
           '<rect width="24" height="24" rx="5" fill="#4a9eff"/>'
           '<path d="M4 17l5-5 4 4 7-7" fill="none" stroke="#fff" '
           'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>')
    return Response(svg, mimetype="image/svg+xml")


# ----------------------------------------------------------------------
# Reference data
# ----------------------------------------------------------------------

@app.route("/api/pairs")
def api_pairs():
    """The pair registry — so the UI builds its controls from the same
    single source of truth the engine uses, instead of a hardcoded copy."""
    return jsonify([
        {
            "name": name,
            "color": cfg["color"],
            "sl_pips": cfg.get("sl_pips", DEFAULT_SL_PIPS),
            "tp_pips": cfg.get("tp_pips", DEFAULT_TP_PIPS),
        }
        for name, cfg in PAIRS.items()
    ])


@app.route("/api/strategies")
def api_strategies():
    """Whatever is in /strategies right now — the picker and its parameter
    controls are built from this, so dropping a file in that folder and
    refreshing is all it takes to see it here. Files that failed to import
    are reported rather than silently missing."""
    strategies = load_strategies()
    return jsonify({
        "strategies": [
            {
                "name": name,
                "label": cfg["label"],
                "description": cfg.get("description", ""),
                "params": cfg["params"],
            }
            for name, cfg in strategies.items()
        ],
        "errors": [{"name": n, "error": e} for n, e in load_errors.items()],
        "defaults": {"start": START, "end": END},
    })


# ----------------------------------------------------------------------
# Backtest
# ----------------------------------------------------------------------

@app.route("/api/backtest", methods=["POST"])
def api_backtest():
    """Runs the backtest for the selected pairs and returns what the page
    needs: one equity series per pair, a pooled trade list, and combined
    stats. Optional start/end narrow the window — which is what makes an
    in-sample / out-of-sample split possible."""
    settings = _backtest_settings(_body())
    series, pooled = _run(settings)

    combined = summarize(pooled, label="Combined", verbose=False)
    combined["exit_reasons"] = pooled["exit_reason"].value_counts().to_dict()

    # Remember it for the Compare page. Same strategy+params replaces itself.
    key = f"{settings['strategy']}|{sorted(settings['params'].items())}"
    SAVED_RUNS[key] = {
        "key": key,
        "strategy": settings["strategy"],
        "strategy_label": (load_strategies().get(settings["strategy"], {})
                           .get("label", settings["strategy"])),
        "params": settings["params"],
        "pairs": settings["pairs"],
        "start": settings["start"],
        "end": settings["end"],
        "stats": combined,
        "series": series,
    }

    return jsonify({
        "series": series,
        "combined": combined,
        "trades": _trade_table(pooled),
        "settings": settings,
    })


# ----------------------------------------------------------------------
# Account — position sizing, margin, real money (core/account.py)
# ----------------------------------------------------------------------

@app.route("/api/account", methods=["POST"])
def api_account():
    """Runs the same backtest, then puts an account behind it: sizes each
    trade by risk, tracks equity and margin, and refuses trades there isn't
    margin for. Answers 'what would this have done to my balance?' rather
    than 'what was the edge per trade?'."""
    body = _body()
    settings = _backtest_settings(body)
    _, pooled = _run(settings)

    account = {
        "initial_balance": _number(body, "initial_balance", 10_000, minimum=1, maximum=1e9),
        "risk_per_trade": _number(body, "risk_per_trade", 0.01, minimum=0.0001, maximum=1),
        "leverage": _number(body, "leverage", 30, minimum=1, maximum=500),
    }
    rows, summary = simulate(pooled, **account)

    return jsonify({
        "summary": summary,
        "trades": [
            {"entry_date": str(r["entry_date"])[:10], "pair": r["pair"],
             "pnl": r["pnl"], "units": r["units"], "taken": r["taken"],
             "skip_reason": r["skip_reason"]}
            for r in rows
        ],
        "settings": {**settings, **account},
    })


# ----------------------------------------------------------------------
# Saved runs — for the Compare page
# ----------------------------------------------------------------------

@app.route("/api/runs")
def api_runs():
    """Every backtest run held in memory. One slot per strategy+params, so
    nothing appears twice. Includes each run's equity series so the Compare
    page can draw the curves without re-running anything."""
    return jsonify([
        {k: run[k] for k in ("key", "strategy", "strategy_label", "params",
                             "pairs", "start", "end", "stats", "series")}
        for run in SAVED_RUNS.values()
    ])


@app.route("/api/runs", methods=["DELETE"])
def api_clear_runs():
    count = len(SAVED_RUNS)
    SAVED_RUNS.clear()
    return jsonify({"cleared": count})


# ----------------------------------------------------------------------
# Journal — for the Tracker page
# ----------------------------------------------------------------------

@app.route("/api/journal/live")
def api_journal_live():
    """Real trades, each with its R alongside — the unit that compares
    directly to the backtest."""
    trades = live_journal.fetch_trades(open_only=request.args.get("open") == "1")
    for t in trades:
        t["r_multiple"] = live_journal.r_multiple(t)
    return jsonify(trades)


@app.route("/api/journal/runs")
def api_journal_runs():
    """Backtest runs saved to the journal database — these survive a restart,
    unlike /api/runs."""
    return jsonify(backtest_journal.list_runs())


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8501, debug=False)
