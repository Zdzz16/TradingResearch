import pandas as pd

def run_backtest(data, stop_loss=None, take_profit=None, max_hold_days=5, allow_overlap=False):
    """
    Generic backtest engine — works with ANY strategy, as long as the data
    has a 'NewSignal' column (True on days a trade should be entered).

    stop_loss: how far price can move against you before exiting, in price
               units (e.g. 0.01 = exit if price drops 100 pips). None = no stop.
    take_profit: how far price must move in your favor to exit early. None = no target.
    max_hold_days: total number of days the trade can stay open, counting the
                   entry day itself as day 1.
    allow_overlap: if False (default), any signal that fires while a previous
                   trade is still open is SKIPPED — matching how one real
                   trading account actually behaves (can't be in the same
                   trade twice at once). Set True only if you deliberately
                   want to measure each signal's edge in isolation.

    Returns a DataFrame — one row per trade, with entry/exit details and WHY
    each trade closed (stop_loss / take_profit / time_exit).
    """
    data = data.reset_index()
    signal_rows = data[data["NewSignal"]].index
    results = []

    # Tracks the row number where the current open trade will exit.
    # None means "no trade currently open."
    last_exit_row = None

    for i in signal_rows:
        entry_row = i + 1
        if entry_row >= len(data):
            continue

        # Skip this signal if a previous trade is still open on entry day
        if not allow_overlap and last_exit_row is not None and entry_row <= last_exit_row:
            continue

        entry_price = data.loc[entry_row, "Open"]
        entry_date = data.loc[entry_row, "Date"]
        exit_price, exit_date, exit_reason = None, None, None
        exit_row = None

        for offset in range(0, max_hold_days):
            row = entry_row + offset
            if row >= len(data):
                break

            low = data.loc[row, "Low"]
            high = data.loc[row, "High"]

            if stop_loss is not None and low <= entry_price - stop_loss:
                exit_price = entry_price - stop_loss
                exit_date = data.loc[row, "Date"]
                exit_reason = "stop_loss"
                exit_row = row
                break

            if take_profit is not None and high >= entry_price + take_profit:
                exit_price = entry_price + take_profit
                exit_date = data.loc[row, "Date"]
                exit_reason = "take_profit"
                exit_row = row
                break

        if exit_price is None:
            row = min(entry_row + max_hold_days - 1, len(data) - 1)
            exit_price = data.loc[row, "Close"]
            exit_date = data.loc[row, "Date"]
            exit_reason = "time_exit"
            exit_row = row

        last_exit_row = exit_row

        results.append({
            "entry_date": entry_date,
            "entry_price": entry_price,
            "exit_date": exit_date,
            "exit_price": exit_price,
            "exit_reason": exit_reason,
            "profit": exit_price - entry_price
        })

    return pd.DataFrame(results)