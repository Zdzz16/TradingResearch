import pandas as pd

# What every strategy must hand the engine, besides a date index.
REQUIRED_COLUMNS = ["Open", "High", "Low", "Close", "NewSignal"]


def run_backtest(data, stop_loss=None, take_profit=None, max_hold_days=5,
                 allow_overlap=False, spread=0.0):
    """
    Generic backtest engine — works with ANY strategy, as long as the data
    has a 'NewSignal' column (True on days a trade should be entered).
    LONG-ONLY for now: every signal is a buy. Short selling gets added
    when a strategy actually needs it, not before.

    stop_loss: how far price can move against you before exiting, in price
               units (e.g. 0.01 = exit if price drops 100 pips). None = no stop.
    take_profit: how far price must move in your favor to exit early. None = no target.
    max_hold_days: total number of days the trade can stay open, counting the
                   entry day itself as day 1.
    allow_overlap: if False (default), signals firing while a trade is open
                   are skipped, matching one real trading account.
    spread: round-trip transaction cost in price units, deducted once from
            every trade's profit — you buy at the ask but sell at the bid,
            so each round trip costs one full spread. 0 = free trading.
            (This models the COST only; stop/target levels are assumed to
            be placed off chart prices and are not shifted.)

    How exits are decided each day, in this order:
      1. If the day OPENS beyond the stop or the target, the trade exits at
         that open — a gap fill happened before anything else that day, so
         it outranks every intrabar guess. Stops fill worse, targets better.
      2. Otherwise, if the day's range touched the stop, exit at the stop.
      3. Otherwise, if it touched the target, exit at the target.
    When one bar's range contains BOTH levels, daily data cannot reveal
    which was touched first. The engine then assumes the STOP — the
    pessimistic choice — and flags that trade with ambiguous=True, so you
    can always see how much of a result rests on this assumption.

    Returns a DataFrame — one row per trade:
      exit_reason: stop_loss / take_profit / time_exit, or end_of_data when
                   the data ran out before the trade could finish properly.
      ambiguous:   True when the exit relied on the pessimistic same-bar
                   assumption described above.
      profit:      exit - entry - spread, in raw price units.
      return_pct:  profit as a fraction of the entry price.
      r_multiple:  profit in units of risk (1R = the stop distance), e.g.
                   -1.0 = lost exactly what was risked. None without a stop.
    """
    data = data.reset_index()

    # Fail loudly on bad input instead of producing silently wrong results.
    # A NaN price would make every comparison against it False, quietly
    # disabling stops and targets for that bar — the worst kind of bug.
    missing = [c for c in REQUIRED_COLUMNS if c not in data.columns]
    if missing:
        raise ValueError(f"Data is missing required column(s): {', '.join(missing)}")
    if "Date" not in data.columns:
        raise ValueError(
            "Data must be indexed by date (like get_data returns it) — "
            "after reset_index no 'Date' column was found."
        )
    bad_rows = data[["Open", "High", "Low", "Close"]].isna().any(axis=1)
    if bad_rows.any():
        first_bad = data.loc[bad_rows, "Date"].iloc[0]
        raise ValueError(
            f"{int(bad_rows.sum())} row(s) have missing OHLC prices "
            f"(first: {first_bad}). Clean the data before backtesting."
        )

    signal_rows = data[data["NewSignal"]].index
    results = []
    last_exit_row = None

    for i in signal_rows:
        entry_row = i + 1
        if entry_row >= len(data):
            continue  # not enough future data to even enter

        if not allow_overlap and last_exit_row is not None and entry_row <= last_exit_row:
            continue

        entry_price = data.loc[entry_row, "Open"]
        entry_date = data.loc[entry_row, "Date"]
        exit_price, exit_date, exit_reason = None, None, None
        exit_row = None
        ambiguous = False

        stop_level = entry_price - stop_loss if stop_loss is not None else None
        target_level = entry_price + take_profit if take_profit is not None else None

        for offset in range(0, max_hold_days):
            row = entry_row + offset
            if row >= len(data):
                break

            day_open = data.loc[row, "Open"]
            low = data.loc[row, "Low"]
            high = data.loc[row, "High"]

            hit_stop = stop_level is not None and low <= stop_level
            hit_target = target_level is not None and high >= target_level

            # 1) Opening gaps first: a fill at the open happened before any
            #    intrabar move, so there is nothing to assume about order.
            if stop_level is not None and day_open <= stop_level:
                exit_price, exit_reason = day_open, "stop_loss"
            elif target_level is not None and day_open >= target_level:
                exit_price, exit_reason = day_open, "take_profit"
            # 2) Intrabar: if the bar contains both levels, the true order
            #    is unknowable from daily data -> assume the stop
            #    (pessimistic) and mark the trade as ambiguous.
            elif hit_stop:
                exit_price, exit_reason = stop_level, "stop_loss"
                ambiguous = hit_target
            elif hit_target:
                exit_price, exit_reason = target_level, "take_profit"

            if exit_price is not None:
                exit_date = data.loc[row, "Date"]
                exit_row = row
                break

        if exit_price is None:
            last_allowed = entry_row + max_hold_days - 1
            if last_allowed <= len(data) - 1:
                row = last_allowed
                exit_reason = "time_exit"       # held the full window
            else:
                row = len(data) - 1
                exit_reason = "end_of_data"     # data ended mid-trade
            exit_price = data.loc[row, "Close"]
            exit_date = data.loc[row, "Date"]
            exit_row = row

        last_exit_row = exit_row

        profit = exit_price - entry_price - spread
        results.append({
            "entry_date": entry_date,
            "entry_price": entry_price,
            "exit_date": exit_date,
            "exit_price": exit_price,
            "exit_reason": exit_reason,
            "ambiguous": ambiguous,
            "profit": profit,
            "return_pct": profit / entry_price,
            "r_multiple": profit / stop_loss if stop_loss is not None else None
        })

    return pd.DataFrame(results)
