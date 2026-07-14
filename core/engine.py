import pandas as pd

# What every strategy must hand the engine, besides a date index.
REQUIRED_COLUMNS = ["Open", "High", "Low", "Close", "NewSignal"]

# Optional per-signal columns a strategy MAY add (read on the signal's row):
#   Direction      +1 = long, -1 = short. Missing/NaN = long.
#   StopDistance   overrides stop_loss for that one signal (price units).
#   TargetDistance overrides take_profit for that one signal (price units).
# This lets a strategy size its stop per setup (e.g. volatility/ATR-based)
# without the engine knowing anything about indicators.

_STOP_REASONS = ("stop_loss", "break_even", "trailing_stop")


def run_backtest(data, stop_loss=None, take_profit=None, max_hold_days=5,
                 allow_overlap=False, spread=0.0, swap_per_night=0.0,
                 slippage=0.0, trailing_stop=None, break_even_at=None):
    """
    Generic daily-bar backtest engine — works with ANY strategy that
    provides a 'NewSignal' column (True on days a trade should be entered).
    Longs and shorts are both supported via the optional Direction column.

    Parameters (all distances/costs in PRICE UNITS):
      stop_loss:      initial stop distance from entry. None = no stop.
                      Per-signal override: 'StopDistance' column.
      take_profit:    target distance from entry. None = no target.
                      Per-signal override: 'TargetDistance' column.
      max_hold_days:  total days a trade may stay open; entry day = day 1.
      allow_overlap:  if False (default), signals firing while a trade is
                      open are skipped, matching one real trading account.
      spread:         round-trip transaction cost, deducted once per trade.
      swap_per_night: financing cost per night held (nights = days_held - 1).
                      Negative = you EARN carry. Same value both directions
                      (a deliberate simplification; real swaps differ by side).
      slippage:       extra adverse fill on STOP-type exits only (stops are
                      market orders in fast conditions; targets are limit
                      orders and fill exactly). A stress knob: raise it to ask
                      "does the edge survive bad fills?" Default 0.
      trailing_stop:  if set, a stop that follows the best price reached,
                      staying this far behind it. Tightens only, never loosens.
      break_even_at:  if set, once the trade has moved this far in your
                      favor, the stop jumps to the entry price.

    How exits are decided on each bar, in this order:
      1. If the bar OPENS beyond the (current) stop or the target, exit at
         that open — a gap fill happened before anything else that day.
         Stops fill worse (minus slippage), targets fill better.
      2. Otherwise, if the bar's range touched the stop, exit at the stop
         (minus slippage).
      3. Otherwise, if it touched the target, exit at the target.
    When one bar's range contains BOTH levels, daily data cannot reveal
    which was touched first: the engine assumes the STOP (pessimistic) and
    flags the trade with ambiguous=True.

    Dynamic stops (trailing / break-even) update conservatively: a bar is
    checked against the stop as it stood BEFORE that bar, and only then may
    the bar's new extreme tighten the stop for the NEXT bar. (Whether a
    bar's high came before its low is unknowable from daily data, so the
    engine never lets a bar tighten a stop and hit it in the same step.)
    Where several stops apply at once, the most protective one is used;
    exit_reason names which kind was binding: stop_loss / break_even /
    trailing_stop.

    Data hygiene ("envelope rule"): some data sources report Opens/Closes
    OUTSIDE the High-Low range. Every reported price is a price that
    traded, so the engine treats each bar's true range as
    [min(O,H,L,C), max(O,H,L,C)]. Truly corrupt bars (High < Low) and NaN
    prices are rejected loudly.

    Returns a DataFrame — one row per trade:
      entry_date, entry_price, exit_date, exit_price
      exit_reason: stop_loss / break_even / trailing_stop / take_profit /
                   time_exit / end_of_data (data ran out mid-trade)
      ambiguous:   exit relied on the pessimistic same-bar assumption
      profit:      side*(exit - entry) - spread - swap*nights, price units
      return_pct:  profit as a fraction of the entry price
      r_multiple:  profit in units of risk (1R = that trade's stop distance);
                   None when the trade had no stop
      direction:   "long" or "short"
      days_held:   trading days from entry to exit, inclusive
      mae / mfe:   Maximum Adverse / Favorable Excursion — the worst and best
                   the trade looked while open, price units, measured on full
                   bars (the exit bar's whole range counts: a documented,
                   conservative overstatement daily data can't avoid).
    """
    # ---------- parameter validation ----------
    if max_hold_days < 1:
        raise ValueError("max_hold_days must be at least 1 (the entry day itself).")
    for name, val in [("stop_loss", stop_loss), ("take_profit", take_profit),
                      ("trailing_stop", trailing_stop), ("break_even_at", break_even_at)]:
        if val is not None and val <= 0:
            raise ValueError(f"{name} must be a positive distance, got {val}.")
    if spread < 0 or slippage < 0:
        raise ValueError("spread and slippage cannot be negative.")

    # ---------- data validation ----------
    data = data.reset_index()

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
    corrupt = data["High"] < data["Low"]
    if corrupt.any():
        first_bad = data.loc[corrupt, "Date"].iloc[0]
        raise ValueError(
            f"{int(corrupt.sum())} row(s) have High < Low — corrupt data "
            f"(first: {first_bad})."
        )

    has_direction = "Direction" in data.columns
    has_stop_col = "StopDistance" in data.columns
    has_target_col = "TargetDistance" in data.columns

    signal_rows = data[data["NewSignal"]].index
    results = []
    last_exit_row = None

    for i in signal_rows:
        entry_row = i + 1
        if entry_row >= len(data):
            continue  # not enough future data to even enter

        if not allow_overlap and last_exit_row is not None and entry_row <= last_exit_row:
            continue

        # ----- per-signal setup (read on the signal's own row) -----
        side = 1
        if has_direction and pd.notna(data.loc[i, "Direction"]):
            side = int(data.loc[i, "Direction"])
            if side not in (1, -1):
                raise ValueError(
                    f"Direction must be +1 (long) or -1 (short), got "
                    f"{data.loc[i, 'Direction']} on {data.loc[i, 'Date']}."
                )
        sig_stop = stop_loss
        if has_stop_col and pd.notna(data.loc[i, "StopDistance"]):
            sig_stop = float(data.loc[i, "StopDistance"])
        sig_target = take_profit
        if has_target_col and pd.notna(data.loc[i, "TargetDistance"]):
            sig_target = float(data.loc[i, "TargetDistance"])
        for name, val in [("StopDistance", sig_stop), ("TargetDistance", sig_target)]:
            if val is not None and val <= 0:
                raise ValueError(
                    f"{name} must be positive, got {val} on {data.loc[i, 'Date']}."
                )

        entry_price = data.loc[entry_row, "Open"]
        entry_date = data.loc[entry_row, "Date"]

        # For a short, "beyond the stop" means ABOVE it and "beyond the
        # target" means BELOW it. Multiplying prices by side (+1/-1) folds
        # both cases into one set of comparisons.
        stop_level = entry_price - side * sig_stop if sig_stop is not None else None
        target_level = entry_price + side * sig_target if sig_target is not None else None

        exit_price, exit_date, exit_reason = None, None, None
        exit_row = None
        ambiguous = False
        best_so_far = entry_price   # best favorable price up to the PREVIOUS bar
        be_armed = False            # break-even stop active yet?
        worst_seen, best_seen = None, None  # full-bar audit extremes (MAE/MFE)

        for offset in range(0, max_hold_days):
            row = entry_row + offset
            if row >= len(data):
                break

            day_open = data.loc[row, "Open"]
            # Envelope rule: the bar's true range must contain every
            # reported price (see docstring).
            bar_hi = max(data.loc[row, "High"], day_open, data.loc[row, "Close"])
            bar_lo = min(data.loc[row, "Low"], day_open, data.loc[row, "Close"])

            # Audit extremes include this bar in full, even if we exit here.
            adverse_px = bar_lo if side == 1 else bar_hi
            favorable_px = bar_hi if side == 1 else bar_lo
            worst_seen = adverse_px if worst_seen is None else (
                min(worst_seen, adverse_px) if side == 1 else max(worst_seen, adverse_px))
            best_seen = favorable_px if best_seen is None else (
                max(best_seen, favorable_px) if side == 1 else min(best_seen, favorable_px))

            # The stop this bar is judged against — as it stood BEFORE the
            # bar. Most protective wins; ties prefer the earlier-listed kind.
            candidates = []
            if stop_level is not None:
                candidates.append((stop_level, "stop_loss"))
            if break_even_at is not None and be_armed:
                candidates.append((entry_price, "break_even"))
            if trailing_stop is not None:
                candidates.append((best_so_far - side * trailing_stop, "trailing_stop"))
            eff_stop, stop_kind = None, None
            for level, kind in candidates:
                if eff_stop is None or side * level > side * eff_stop:
                    eff_stop, stop_kind = level, kind

            hit_stop = eff_stop is not None and side * adverse_px <= side * eff_stop
            hit_target = target_level is not None and side * favorable_px >= side * target_level

            # 1) Opening gaps first — a fill at the open happened before
            #    any intrabar move, so there is nothing to assume.
            if eff_stop is not None and side * day_open <= side * eff_stop:
                exit_price, exit_reason = day_open - side * slippage, stop_kind
            elif target_level is not None and side * day_open >= side * target_level:
                exit_price, exit_reason = day_open, "take_profit"
            # 2) Intrabar: both levels in one bar -> true order unknowable
            #    -> assume the stop (pessimistic) and flag it.
            elif hit_stop:
                exit_price, exit_reason = eff_stop - side * slippage, stop_kind
                ambiguous = hit_target
            elif hit_target:
                exit_price, exit_reason = target_level, "take_profit"

            if exit_price is not None:
                exit_date = data.loc[row, "Date"]
                exit_row = row
                break

            # Survived the bar: only NOW may it tighten dynamic stops
            # (for the NEXT bar) and arm the break-even.
            if side * favorable_px > side * best_so_far:
                best_so_far = favorable_px
            if break_even_at is not None and not be_armed \
                    and side * (best_so_far - entry_price) >= break_even_at:
                be_armed = True

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

        nights = exit_row - entry_row
        profit = side * (exit_price - entry_price) - spread - swap_per_night * nights
        results.append({
            "entry_date": entry_date,
            "entry_price": entry_price,
            "exit_date": exit_date,
            "exit_price": exit_price,
            "exit_reason": exit_reason,
            "ambiguous": ambiguous,
            "profit": profit,
            "return_pct": profit / entry_price,
            "r_multiple": profit / sig_stop if sig_stop is not None else None,
            "direction": "long" if side == 1 else "short",
            "days_held": exit_row - entry_row + 1,
            "mae": max(0.0, side * (entry_price - worst_seen)),
            "mfe": max(0.0, side * (best_seen - entry_price)),
        })

    return pd.DataFrame(results)
