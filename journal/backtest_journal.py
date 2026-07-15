"""
Backtest journal — saves and reads runs produced by the backtesting engine.

A "run" is one backtest: its trades share a run_id so you can pull them back
as a set, compare runs, or drop one without touching the others.

The engine speaks its own language (long/short, r_multiple, entry_date); this
module translates it into the shared schema in storage.py, so a saved backtest
trade is shaped exactly like a live one.
"""

from datetime import datetime, timezone

from journal import storage

TABLE = storage.BACKTEST_TABLE

# engine -> shared schema
DIRECTION_MAP = {"long": "buy", "short": "sell"}


def _stamp(value):
    """Engine dates are pandas Timestamps; the schema stores ISO strings."""
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat(sep=" ", timespec="seconds")
    return str(value)


def _to_row(trade, asset, run_id):
    direction = DIRECTION_MAP.get(str(trade.get("direction", "long")).lower())
    if direction is None:
        raise ValueError(
            f"Unexpected direction {trade.get('direction')!r} — expected 'long' or 'short'."
        )
    # r_multiple = profit / stop_distance, so the stop distance the engine
    # actually used is recoverable from the pair. Keeps R computable later
    # without re-running the backtest.
    stop_distance = None
    r = trade.get("r_multiple")
    profit = trade.get("profit")
    if r not in (None, 0) and profit is not None and r == r:  # r == r filters NaN
        stop_distance = abs(profit / r)

    return {
        "run_id": run_id,
        "asset": asset,
        "direction": direction,
        "entry_timestamp": _stamp(trade.get("entry_date")),
        "exit_timestamp": _stamp(trade.get("exit_date")),
        "entry_price": trade.get("entry_price"),
        "exit_price": trade.get("exit_price"),
        # The engine models price, not position size — there is no lot size to
        # record until the sizing layer exists. NULL is the honest answer.
        "volume": None,
        "profit": profit,
        "stop_distance": stop_distance,
        "exit_reason": trade.get("exit_reason"),
        "notes": None,
    }


def save_run(trades, asset, run_id=None, replace=True):
    """
    Saves one backtest's trades and returns the run_id.

    trades:  the engine's DataFrame (or any list of dicts with its columns).
    asset:   which instrument this run was on, e.g. "EURUSD".
    run_id:  a name for this run. Defaults to a timestamped one.
    replace: True (default) wipes any run already stored under this run_id and
             asset before writing — so re-running the same thing updates it
             instead of stacking a second copy.
    """
    if run_id is None:
        run_id = f"{asset}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    records = trades.to_dict("records") if hasattr(trades, "to_dict") else list(trades)
    rows = [_to_row(t, asset, run_id) for t in records]

    if replace:
        storage.delete(TABLE, "run_id = ? AND asset = ?", (run_id, asset))
    storage.insert(TABLE, rows)
    return run_id


def fetch_run(run_id):
    """Every trade saved under one run_id, oldest first."""
    return storage.fetch(TABLE, "run_id = ?", (run_id,))


def fetch_all():
    """Every backtest trade ever saved."""
    return storage.fetch(TABLE)


def list_runs():
    """A summary per saved run: how many trades, over what dates, total P/L."""
    runs = {}
    for trade in storage.fetch(TABLE):
        key = (trade["run_id"], trade["asset"])
        run = runs.setdefault(key, {
            "run_id": trade["run_id"], "asset": trade["asset"],
            "trades": 0, "profit": 0.0, "first_entry": None, "last_exit": None,
        })
        run["trades"] += 1
        run["profit"] += trade["profit"] or 0.0
        if run["first_entry"] is None:
            run["first_entry"] = trade["entry_timestamp"]
        if trade["exit_timestamp"]:
            run["last_exit"] = max(run["last_exit"] or "", trade["exit_timestamp"])
    for run in runs.values():
        run["profit"] = round(run["profit"], 5)
    return list(runs.values())


def delete_run(run_id):
    """Drops one run. Returns how many trades went."""
    return storage.delete(TABLE, "run_id = ?", (run_id,))
