import pandas as pd

# What every strategy must hand the engine, besides a date index.
REQUIRED_COLUMNS = ["Open", "High", "Low", "Close", "NewSignal"]

# Optional per-signal columns a strategy MAY add (read on the signal's row):
#   Direction      +1 = long, -1 = short. Missing/NaN = long.
#   StopDistance   overrides stop_loss for that one signal (price units).
#   TargetDistance overrides take_profit for that one signal (price units).
#   EntryLimit     a PRICE: instead of entering at the next open, rest a
#                  limit order there for entry_valid_days bars. Fills when
#                  touched (or better, on a gap); expires unfilled otherwise.
# Optional per-bar column:
#   ExitSignal     True = close any open trade at the NEXT bar's open
#                  (same one-bar delay as entries — you see the condition
#                  at the close, you act at the next open).


def run_backtest(data, stop_loss=None, take_profit=None, max_hold_days=5,
                 allow_overlap=False, max_open_trades=None, spread=0.0,
                 commission_pct=0.0, swap_per_night=0.0, slippage=0.0,
                 trailing_stop=None, break_even_at=None,
                 entry_valid_days=5, ambiguous_policy="stop"):
    """
    Event-driven bar-by-bar backtest engine — works with ANY strategy that
    provides a 'NewSignal' column. Longs and shorts both supported. Although
    parameter names say "days", nothing assumes daily bars: feed it hourly
    bars and every "day" simply means "bar".

    Parameters (all distances/costs in PRICE UNITS):
      stop_loss / take_profit: initial stop/target distance from entry.
                  None = none. Per-signal overrides: StopDistance /
                  TargetDistance columns.
      max_hold_days: bars a trade may stay open; entry bar = day 1.
      allow_overlap: False (default) = one position at a time.
      max_open_trades: positions allowed at once; overrides allow_overlap
                  when set (allow_overlap False = 1, True = unlimited).
                  A signal arriving while full is skipped, like a trader
                  who is already fully positioned.
      spread:     round-trip transaction cost, deducted once per trade.
      commission_pct: round-trip commission as a fraction of the entry
                  price (e.g. 0.0002 = 2 basis points) — for instruments
                  charged by value rather than by spread.
      swap_per_night: financing cost per night held (nights = days_held-1).
                  Negative = you EARN carry. Same value both directions.
      slippage:   extra adverse fill on STOP-type exits only (stops are
                  market orders in fast conditions; targets/planned exits
                  are limit or scheduled orders). A stress knob, default 0.
      trailing_stop: stop that follows the best price reached, this far
                  behind it. Tightens only.
      break_even_at: once the trade is this far in profit, the stop jumps
                  to the entry price.
      entry_valid_days: how many bars an EntryLimit order stays working
                  before it expires unfilled.
      ambiguous_policy: what to assume when one bar touches BOTH stop and
                  target (the true order is unknowable from bar data):
                  "stop" (default, pessimistic) or "target" (optimistic).
                  Run both and the truth lies between — the gap between
                  the two results measures how much the data's resolution
                  limits what you can know. Never trade the optimistic one.

    How each bar is processed, in order:
      1. Open positions check their exits:
         a. Events AT THE OPEN, worst first: gap past the stop (fill at
            open minus slippage), gap past the target (fill at open —
            better), then a scheduled ExitSignal exit (market at open).
         b. Intrabar: stop touched -> exit at stop (minus slippage);
            target touched -> exit at target. Both touched -> follow
            ambiguous_policy and flag the trade ambiguous=True.
         c. Dynamic stops (trailing / break-even) update conservatively:
            a bar is judged against the stop as it stood BEFORE the bar;
            only a survived bar may tighten the stop for the NEXT bar.
            Where several stops apply, the most protective binds, and
            exit_reason names which kind: stop_loss / break_even /
            trailing_stop.
         d. Out of time -> exit at the bar's close ("time_exit"), or
            "end_of_data" if the data ends before the window does.
      2. Pending entry orders try to fill. Market orders (no EntryLimit)
         fill at the open one bar after the signal. Limit orders fill when
         the bar touches the limit (at the open if it gapped through —
         better). A fill is skipped if positions are at max_open_trades.
         On the FILL BAR of a limit order the target is not checked:
         price beyond the target cannot be proven to have happened AFTER
         the mid-bar fill (the stop is checked — reaching it requires
         passing through the limit first). Market fills check both,
         exactly as before.
      3. New signals become orders that activate next bar.

    Data hygiene ("envelope rule"): some sources report Opens/Closes
    OUTSIDE the High-Low range (Yahoo FX does, often). Every reported
    price traded, so a bar's true range is [min(O,H,L,C), max(O,H,L,C)].
    NaN prices and High < Low are rejected loudly.

    Returns a DataFrame — one row per trade, in entry order:
      entry_date, entry_price, exit_date, exit_price
      entry_type:  "market" or "limit"
      exit_reason: stop_loss / break_even / trailing_stop / take_profit /
                   exit_signal / time_exit / end_of_data
      ambiguous:   exit relied on the same-bar assumption (see above)
      profit:      side*(exit-entry) - spread - commission - swap*nights
      return_pct:  profit as a fraction of the entry price
      r_multiple:  profit in units of risk (1R = that trade's stop
                   distance); None when the trade had no stop
      direction:   "long" or "short"
      days_held:   bars from entry to exit, inclusive
      mae / mfe:   worst / best the trade looked while open (price units),
                   measured on full bars — the exit bar's whole range
                   counts, a documented conservative overstatement.
    """
    # ---------- parameter validation ----------
    if max_hold_days < 1:
        raise ValueError("max_hold_days must be at least 1 (the entry day itself).")
    if entry_valid_days < 1:
        raise ValueError("entry_valid_days must be at least 1.")
    if max_open_trades is not None and max_open_trades < 1:
        raise ValueError("max_open_trades must be at least 1 when set.")
    if ambiguous_policy not in ("stop", "target"):
        raise ValueError('ambiguous_policy must be "stop" or "target".')
    for name, val in [("stop_loss", stop_loss), ("take_profit", take_profit),
                      ("trailing_stop", trailing_stop), ("break_even_at", break_even_at)]:
        if val is not None and val <= 0:
            raise ValueError(f"{name} must be a positive distance, got {val}.")
    if spread < 0 or slippage < 0 or commission_pct < 0:
        raise ValueError("spread, slippage and commission_pct cannot be negative.")

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

    n = len(data)
    O = data["Open"].tolist()
    H = data["High"].tolist()
    L = data["Low"].tolist()
    C = data["Close"].tolist()
    DATES = data["Date"].tolist()
    SIG = data["NewSignal"].tolist()

    def col(name):
        return data[name].tolist() if name in data.columns else None

    DIR, SDIST, TDIST = col("Direction"), col("StopDistance"), col("TargetDistance")
    ELIM, XSIG = col("EntryLimit"), col("ExitSignal")

    def given(lst, i):
        """Value from an optional column, or None when absent/NaN."""
        if lst is None:
            return None
        v = lst[i]
        return None if v is None or pd.isna(v) else v

    cap = max_open_trades if max_open_trades is not None \
        else (float("inf") if allow_overlap else 1)

    orders = []     # entry orders waiting to fill, in signal order
    open_pos = []   # live positions, in the order they were opened
    finished = []
    seq = 0         # global creation counter, keeps output deterministic

    # ---------- per-position helpers (close over the current bar) ----------
    def dynamic_stop(pos):
        """The stop this bar is judged against — most protective wins;
        ties prefer stop_loss over break_even over trailing_stop."""
        side = pos["side"]
        cur, kind = pos["stop_level"], "stop_loss"
        if break_even_at is not None and pos["be_armed"]:
            if cur is None or side * pos["entry_price"] > side * cur:
                cur, kind = pos["entry_price"], "break_even"
        if trailing_stop is not None:
            trail = pos["best"] - side * trailing_stop
            if cur is None or side * trail > side * cur:
                cur, kind = trail, "trailing_stop"
        return (cur, kind) if cur is not None else (None, None)

    for t in range(n):
        o = O[t]
        bar_hi = max(H[t], o, C[t])   # envelope rule
        bar_lo = min(L[t], o, C[t])
        closed_this_bar = 0
        opened_this_bar = 0

        def try_exit(pos, open_events, suppress_target):
            """Exit price/reason/ambiguous for this bar, or None."""
            side = pos["side"]
            adverse = bar_lo if side == 1 else bar_hi
            favorable = bar_hi if side == 1 else bar_lo
            eff, kind = dynamic_stop(pos)
            tgt = pos["target_level"] if not suppress_target else None
            if open_events:
                if eff is not None and side * o <= side * eff:
                    return o - side * slippage, kind, False
                if tgt is not None and side * o >= side * tgt:
                    return o, "take_profit", False
                if pos["pending_exit"]:
                    return o, "exit_signal", False
            hit_stop = eff is not None and side * adverse <= side * eff
            hit_tgt = tgt is not None and side * favorable >= side * tgt
            if hit_stop and hit_tgt:
                if ambiguous_policy == "target":
                    return tgt, "take_profit", True
                return eff - side * slippage, kind, True
            if hit_stop:
                return eff - side * slippage, kind, False
            if hit_tgt:
                return tgt, "take_profit", False
            return None

        def track_bar(pos):
            """Audit extremes include every bar in full, exit bar too."""
            side = pos["side"]
            adverse = bar_lo if side == 1 else bar_hi
            favorable = bar_hi if side == 1 else bar_lo
            if pos["worst_seen"] is None or side * adverse < side * pos["worst_seen"]:
                pos["worst_seen"] = adverse
            if pos["best_seen"] is None or side * favorable > side * pos["best_seen"]:
                pos["best_seen"] = favorable

        def survive_bar(pos):
            """A survived bar may tighten dynamic stops for the NEXT bar
            and schedule an ExitSignal exit for the next open."""
            side = pos["side"]
            favorable = bar_hi if side == 1 else bar_lo
            if side * favorable > side * pos["best"]:
                pos["best"] = favorable
            if break_even_at is not None and not pos["be_armed"] \
                    and side * (pos["best"] - pos["entry_price"]) >= break_even_at:
                pos["be_armed"] = True
            if given(XSIG, t):
                pos["pending_exit"] = True

        def finalize(pos, price, reason, amb):
            side = pos["side"]
            nights = t - pos["entry_row"]
            profit = side * (price - pos["entry_price"]) - spread \
                - commission_pct * pos["entry_price"] - swap_per_night * nights
            finished.append({
                "_entry_row": pos["entry_row"], "_seq": pos["seq"],
                "entry_date": DATES[pos["entry_row"]],
                "entry_price": pos["entry_price"],
                "exit_date": DATES[t],
                "exit_price": price,
                "exit_reason": reason,
                "ambiguous": amb,
                "profit": profit,
                "return_pct": profit / pos["entry_price"],
                "r_multiple": profit / pos["sig_stop"] if pos["sig_stop"] is not None else None,
                "direction": "long" if side == 1 else "short",
                "entry_type": pos["entry_type"],
                "days_held": t - pos["entry_row"] + 1,
                "mae": max(0.0, side * (pos["entry_price"] - pos["worst_seen"])),
                "mfe": max(0.0, side * (pos["best_seen"] - pos["entry_price"])),
            })

        # ---- 1) exits for open positions ----
        surviving = []
        for pos in open_pos:
            track_bar(pos)
            res = try_exit(pos, open_events=True, suppress_target=False)
            if res is None and t == pos["entry_row"] + max_hold_days - 1:
                res = (C[t], "time_exit", False)
            if res is None and t == n - 1:
                res = (C[t], "end_of_data", False)
            if res is not None:
                finalize(pos, *res)
                closed_this_bar += 1
            else:
                survive_bar(pos)
                surviving.append(pos)
        open_pos = surviving

        # ---- 2) pending entry orders try to fill ----
        for order in orders:
            if order["done"] or t < order["activate"]:
                continue
            if t > order["expire"]:
                order["done"] = True
                continue
            side, limit = order["side"], order["limit"]
            if limit is None:
                fill = o                       # market at the open
                gapped_through = True          # an open fill: nothing pre-dates it
            else:
                touched = bar_lo <= limit if side == 1 else bar_hi >= limit
                if not touched:
                    continue                   # still working, try again next bar
                gapped_through = (side * o <= side * limit)
                fill = o if gapped_through else limit
            order["done"] = True
            if len(open_pos) + closed_this_bar + opened_this_bar >= cap:
                continue                       # fully positioned: order skipped
            pos = {
                "seq": order["seq"], "side": side,
                "entry_row": t, "entry_price": fill,
                "entry_type": "market" if limit is None else "limit",
                "sig_stop": order["sig_stop"],
                "stop_level": fill - side * order["sig_stop"] if order["sig_stop"] is not None else None,
                "target_level": fill + side * order["sig_target"] if order["sig_target"] is not None else None,
                "best": fill, "be_armed": False, "pending_exit": False,
                "worst_seen": None, "best_seen": None,
            }
            opened_this_bar += 1
            track_bar(pos)
            # Fill-bar exits: at-open events already passed; a mid-bar limit
            # fill also can't prove the target was reached AFTER the fill.
            res = try_exit(pos, open_events=False,
                           suppress_target=(limit is not None and not gapped_through))
            if res is None and max_hold_days == 1:
                res = (C[t], "time_exit", False)
            if res is None and t == n - 1:
                res = (C[t], "end_of_data", False)
            if res is not None:
                finalize(pos, *res)
                closed_this_bar += 1
            else:
                survive_bar(pos)
                open_pos.append(pos)

        # ---- 3) new signals become orders for the next bar ----
        if SIG[t] and t + 1 < n:
            side = given(DIR, t)
            side = 1 if side is None else int(side)
            if side not in (1, -1):
                raise ValueError(
                    f"Direction must be +1 (long) or -1 (short), got "
                    f"{DIR[t]} on {DATES[t]}."
                )
            sig_stop = given(SDIST, t)
            sig_stop = stop_loss if sig_stop is None else float(sig_stop)
            sig_target = given(TDIST, t)
            sig_target = take_profit if sig_target is None else float(sig_target)
            for pname, val in [("StopDistance", sig_stop), ("TargetDistance", sig_target)]:
                if val is not None and val <= 0:
                    raise ValueError(f"{pname} must be positive, got {val} on {DATES[t]}.")
            limit = given(ELIM, t)
            if limit is not None and limit <= 0:
                raise ValueError(f"EntryLimit must be a positive price, got {limit} on {DATES[t]}.")
            orders.append({
                "seq": seq, "side": side, "limit": limit,
                "sig_stop": sig_stop, "sig_target": sig_target,
                "activate": t + 1,
                "expire": t + 1 if limit is None else t + entry_valid_days,
                "done": False,
            })
            seq += 1

    finished.sort(key=lambda r: (r["_entry_row"], r["_seq"]))
    for r in finished:
        del r["_entry_row"], r["_seq"]
    return pd.DataFrame(finished)
