"""
Live journal — real trades, in the same shape as backtest trades.

Two ways in:
  * by hand, right now — open_trade() when you enter, close_trade() when you
    exit. You supply the reasoning; nothing else knows it.
  * from the broker, later — broker_sync.py will fill these same rows
    automatically once a broker is chosen.

Because the schema matches the backtest journal exactly, the same analysis and
the same UI work on both, and "did live match the backtest?" becomes a
question you can actually answer.
"""

from datetime import datetime, timezone

from journal import storage

TABLE = storage.LIVE_TABLE

DIRECTIONS = ("buy", "sell")


def _now():
    return datetime.now(timezone.utc).isoformat(sep=" ", timespec="seconds")


def open_trade(asset, direction, entry_price, volume=None, stop_distance=None,
               entry_timestamp=None, run_id=None, notes=None):
    """
    Records a trade you've just entered. Returns its id — you need that id to
    close it later.

    stop_distance: how far your stop sits from entry, in price units. Log it
                   NOW: it can't be recovered afterwards, and without it this
                   trade has no R-multiple, which is the only unit that
                   compares to the backtest. Optional, but you'll want it.
    run_id:        optional — the broker's ticket/order id, once we sync one.
    """
    direction = str(direction).lower()
    if direction not in DIRECTIONS:
        raise ValueError(f"direction must be 'buy' or 'sell', got {direction!r}.")
    if entry_price is None:
        raise ValueError("entry_price is required.")
    if stop_distance is not None and stop_distance <= 0:
        raise ValueError(f"stop_distance must be a positive distance, got {stop_distance}.")

    ids = storage.insert(TABLE, [{
        "run_id": run_id,
        "asset": asset,
        "direction": direction,
        "entry_timestamp": entry_timestamp or _now(),
        "exit_timestamp": None,
        "entry_price": entry_price,
        "exit_price": None,
        "volume": volume,
        "profit": None,
        "stop_distance": stop_distance,
        "exit_reason": None,
        "notes": notes,
    }])
    return ids[0]


def close_trade(trade_id, exit_price, exit_timestamp=None, exit_reason=None,
                profit=None, notes=None):
    """
    Closes an open trade. Raises KeyError if that id doesn't exist, and
    refuses to close one that's already closed — the old journal would
    silently invent a row for a bad index, in the real-money record.

    profit: computed for you from direction, prices and volume if you don't
            pass it. Pass it to record what the broker actually credited
            (fees, financing and slippage included).
    """
    trade = get_trade(trade_id)
    if trade is None:
        raise KeyError(f"No live trade with id {trade_id}.")
    if trade["exit_timestamp"] is not None:
        raise ValueError(
            f"Trade {trade_id} is already closed (exited {trade['exit_timestamp']})."
        )

    if profit is None:
        side = 1 if trade["direction"] == "buy" else -1
        profit = side * (exit_price - trade["entry_price"])
        if trade["volume"]:
            profit *= trade["volume"]

    values = {
        "exit_price": exit_price,
        "exit_timestamp": exit_timestamp or _now(),
        "profit": profit,
        "exit_reason": exit_reason or "manual",
    }
    if notes is not None:
        values["notes"] = notes

    storage.update(TABLE, trade_id, values)
    return get_trade(trade_id)


def get_trade(trade_id):
    """One trade by id, or None."""
    rows = storage.fetch(TABLE, "id = ?", (trade_id,))
    return rows[0] if rows else None


def fetch_trades(open_only=False):
    """Every live trade, oldest first. open_only=True for still-running ones."""
    if open_only:
        return storage.fetch(TABLE, "exit_timestamp IS NULL")
    return storage.fetch(TABLE)


def r_multiple(trade):
    """
    This trade's result in units of risk — the number that compares directly
    to the backtest. None when the trade is still open, or when no stop
    distance was logged at entry (in which case there's nothing to divide by).
    """
    if trade["profit"] is None or not trade["stop_distance"]:
        return None
    risk = trade["stop_distance"] * (trade["volume"] or 1)
    return trade["profit"] / risk
