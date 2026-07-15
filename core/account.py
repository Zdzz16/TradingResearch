"""
Account simulator — turns a list of trades into money.

The engine answers "what trades happened, at what prices, risking how far".
It deliberately knows nothing about your balance: at retail size, how much you
bet doesn't move the market, so position size can't change a fill. This module
is the other half — it walks the trades in date order and applies an account
to them: sizing each position by risk, tracking equity, used margin and free
margin, and **refusing trades there isn't margin for**.

Why this is a separate layer rather than something inside run_backtest():
run_backtest() sees ONE pair. Margin is an account-wide constraint — your
EURUSD position eats margin your gold trade then can't have. A per-pair loop
physically cannot see that. Feed this the combined trade list from every pair
and the constraint is enforced where it actually exists.

Order matters here in a way it doesn't in the engine: equity compounds, so
each trade's size depends on how the ones before it went.

What it models
--------------
  * fixed-fractional sizing — risk a set % of CURRENT equity per trade
  * leverage and margin — margin = position value / leverage, held until exit
  * free margin — equity minus margin already in use; a trade that needs more
    than is free is skipped, exactly as a broker would reject it
  * currency — a EURUSD move pays USD; a USDJPY move pays JPY and is converted

Documented simplifications (be aware before trusting a number)
-------------------------------------------------------------
  * Account currency is USD, and every pair here is USD-based or USD-quoted.
    A cross like EURGBP would need a third rate and is not supported.
  * USDJPY profit is converted at the trade's own exit price. A broker uses
    the rate at the moment of closing; on daily bars that IS the exit price.
  * Margin is checked at entry and released at exit. Intra-trade margin calls
    (a floating loss eating your free margin) are NOT modelled — so this
    answers "could I open it?", not "would I have survived it?".
  * Equity is realised-only: it moves when a trade closes, not while it runs.
"""

from core.pairs import get_pair


def _quote_to_usd(pair_cfg, price):
    """What one unit of the quote currency is worth in USD.

    A EURUSD move already pays USD, so the rate is 1. A USDJPY move pays JPY,
    and since the pair's own price IS how many JPY one USD costs, dividing by
    it converts back.
    """
    if pair_cfg["quote"] == "USD":
        return 1.0
    if pair_cfg["base"] == "USD":       # USDJPY and friends
        return 1.0 / price
    raise ValueError(
        f"Can't convert {pair_cfg['quote']} to USD without a third rate — "
        "cross pairs aren't supported yet."
    )


def _position_value_usd(pair_cfg, units, price):
    """What the position is worth in USD — the number margin is charged on.

    You're holding `units` of the BASE asset. If the base is already USD
    (USDJPY), that's just the unit count. Otherwise each unit costs `price`
    of the quote currency, converted to USD.
    """
    if pair_cfg["base"] == "USD":
        return units
    return units * price * _quote_to_usd(pair_cfg, price)


def simulate(trades, initial_balance=10_000.0, risk_per_trade=0.01,
             leverage=30.0, pair=None):
    """
    Runs an account over a trade list and returns (rows, summary).

    trades: the engine's output. Needs entry_date, exit_date, entry_price,
            exit_price, profit, direction, r_multiple. Multi-pair lists need a
            'pair' column; single-pair lists can pass pair="EURUSD" instead.
    risk_per_trade: fraction of CURRENT equity to risk per trade (0.01 = 1%).
    leverage: 30 = a €30,000 position needs €1,000 of margin.

    Each row adds: units, position_value, margin_required, pnl, equity_after,
    and taken/skip_reason — because a trade the account couldn't afford is
    part of the answer, not something to hide.
    """
    if initial_balance <= 0:
        raise ValueError("initial_balance must be positive.")
    if not 0 < risk_per_trade <= 1:
        raise ValueError("risk_per_trade is a fraction of equity, e.g. 0.01 for 1%.")
    if leverage <= 0:
        raise ValueError("leverage must be positive.")

    records = trades.to_dict("records") if hasattr(trades, "to_dict") else list(trades)
    records = sorted(records, key=lambda t: t["entry_date"])

    equity = initial_balance
    open_positions = []          # (exit_date, margin, pnl) still running
    peak = initial_balance
    max_dd = 0.0
    rows = []

    for trade in records:
        # Release margin and bank the result of anything that closed before
        # this trade opens — that's what frees up room for it.
        still_open = []
        for pos in open_positions:
            if pos["exit_date"] <= trade["entry_date"]:
                equity += pos["pnl"]
                peak = max(peak, equity)
                max_dd = max(max_dd, peak - equity)
            else:
                still_open.append(pos)
        open_positions = still_open

        used_margin = sum(p["margin"] for p in open_positions)
        free_margin = equity - used_margin

        cfg = get_pair(trade.get("pair", pair))
        row = dict(trade)

        # How far the stop sat, in price units. r_multiple = profit / stop,
        # so the engine's own numbers give it back without re-deriving it.
        r = trade.get("r_multiple")
        stop_distance = None
        if r not in (None, 0) and r == r and trade.get("profit") is not None:
            stop_distance = abs(trade["profit"] / r)

        if not stop_distance:
            row.update(taken=False, skip_reason="no stop distance — cannot size by risk",
                       units=0.0, position_value=0.0, margin_required=0.0,
                       pnl=0.0, equity_after=equity)
            rows.append(row)
            continue

        # Size it: risk this many dollars, lose exactly that if the stop hits.
        risk_usd = equity * risk_per_trade
        usd_per_price_unit = _quote_to_usd(cfg, trade["entry_price"])
        units = risk_usd / (stop_distance * usd_per_price_unit)

        value = _position_value_usd(cfg, units, trade["entry_price"])
        margin_required = value / leverage

        if margin_required > free_margin:
            row.update(taken=False,
                       skip_reason=f"needs ${margin_required:,.0f} margin, "
                                   f"${free_margin:,.0f} free",
                       units=0.0, position_value=value,
                       margin_required=margin_required, pnl=0.0,
                       equity_after=equity)
            rows.append(row)
            continue

        # profit is in the quote currency; convert at the exit.
        pnl = trade["profit"] * units * _quote_to_usd(cfg, trade["exit_price"])

        open_positions.append({"exit_date": trade["exit_date"],
                               "margin": margin_required, "pnl": pnl})
        row.update(taken=True, skip_reason=None, units=units,
                   position_value=value, margin_required=margin_required,
                   pnl=pnl, equity_after=equity)  # equity moves when it closes
        rows.append(row)

    # settle whatever was still running at the end
    for pos in open_positions:
        equity += pos["pnl"]
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)

    taken = [r for r in rows if r["taken"]]
    summary = {
        "initial_balance": round(initial_balance, 2),
        "final_equity": round(equity, 2),
        "return_pct": round((equity / initial_balance - 1) * 100, 2),
        "max_drawdown_usd": round(max_dd, 2),
        "max_drawdown_pct": round(max_dd / peak * 100, 2) if peak else 0.0,
        "trades_taken": len(taken),
        "trades_skipped": len(rows) - len(taken),
        "risk_per_trade_pct": round(risk_per_trade * 100, 2),
        "leverage": leverage,
    }
    return rows, summary
