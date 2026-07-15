import pandas as pd
import pytest

from core.account import simulate


def trade(entry, exit_, profit, r, pair="EURUSD", direction="long",
          entry_date="2024-01-01", exit_date="2024-01-05"):
    return {
        "entry_date": pd.Timestamp(entry_date), "exit_date": pd.Timestamp(exit_date),
        "entry_price": entry, "exit_price": exit_, "profit": profit,
        "r_multiple": r, "direction": direction, "pair": pair,
    }


# ---------- sizing ----------

def test_risking_one_percent_loses_exactly_one_percent_on_a_stop():
    """The whole point of fixed-fractional sizing: a -1R trade must cost
    exactly the risk budget, whatever the stop distance happens to be."""
    t = trade(1.10, 1.09, -0.01, -1.0)  # 100-pip stop, stopped out
    rows, summary = simulate([t], initial_balance=10_000, risk_per_trade=0.01)
    assert rows[0]["taken"]
    assert round(rows[0]["pnl"], 2) == -100.0        # 1% of 10,000
    assert round(summary["final_equity"], 2) == 9_900.0


def test_a_tighter_stop_buys_a_bigger_position_for_the_same_risk():
    wide = simulate([trade(1.10, 1.09, -0.01, -1.0)], initial_balance=10_000)[0][0]
    tight = simulate([trade(1.10, 1.095, -0.005, -1.0)], initial_balance=10_000)[0][0]
    assert tight["units"] == pytest.approx(wide["units"] * 2)
    # ...but both still lose exactly the same money
    assert round(tight["pnl"], 2) == round(wide["pnl"], 2) == -100.0


def test_a_two_r_winner_makes_twice_the_risk():
    t = trade(1.10, 1.12, 0.02, 2.0)
    rows, summary = simulate([t], initial_balance=10_000, risk_per_trade=0.01)
    assert round(rows[0]["pnl"], 2) == 200.0
    assert round(summary["final_equity"], 2) == 10_200.0
    assert summary["return_pct"] == 2.0


def test_equity_compounds_so_order_matters():
    """Second trade risks 1% of the NEW balance, not the starting one."""
    ts = [trade(1.10, 1.12, 0.02, 2.0, entry_date="2024-01-01", exit_date="2024-01-02"),
          trade(1.10, 1.09, -0.01, -1.0, entry_date="2024-01-03", exit_date="2024-01-04")]
    rows, summary = simulate(ts, initial_balance=10_000, risk_per_trade=0.01)
    assert round(rows[0]["pnl"], 2) == 200.0     # 1% of 10,000
    assert round(rows[1]["pnl"], 2) == -102.0    # 1% of 10,200
    assert round(summary["final_equity"], 2) == 10_098.0


# ---------- currency ----------

def test_usdjpy_profit_is_converted_from_yen():
    """A USDJPY move pays JPY. Risking $100 with a 1.00 (100-pip) stop means
    100/(1.00 x (1/150)) = 15,000 units; a -1R exit at 149.00 pays
    -1.00 x 15,000 JPY = -15,000 JPY = -$100.67 at that rate. It is NOT
    exactly -$100 precisely because the yen moved between entry and exit —
    that asymmetry is real, and pretending otherwise would be the bug."""
    t = trade(150.00, 149.00, -1.00, -1.0, pair="USDJPY")
    rows, _ = simulate([t], initial_balance=10_000, risk_per_trade=0.01)
    assert rows[0]["units"] == pytest.approx(15_000, rel=1e-9)
    assert rows[0]["pnl"] == pytest.approx(-15_000 / 149.00, rel=1e-9)
    assert -101.0 < rows[0]["pnl"] < -100.0


def test_usd_based_pair_values_the_position_in_units_not_price():
    """USDJPY's base IS dollars: 15,000 units is a $15,000 position. A
    EURUSD position of 15,000 EUR is worth 15,000 x the rate."""
    jpy = simulate([trade(150.00, 149.00, -1.00, -1.0, pair="USDJPY")],
                   initial_balance=10_000)[0][0]
    assert jpy["position_value"] == pytest.approx(jpy["units"])

    eur = simulate([trade(1.10, 1.09, -0.01, -1.0, pair="EURUSD")],
                   initial_balance=10_000)[0][0]
    assert eur["position_value"] == pytest.approx(eur["units"] * 1.10)


def test_gold_pays_dollars_per_ounce():
    # $100 risk with a $20 stop = 5 ounces; +$40 move = +$200
    t = trade(2000.0, 2040.0, 40.0, 2.0, pair="XAUUSD")
    rows, _ = simulate([t], initial_balance=10_000, risk_per_trade=0.01)
    assert rows[0]["units"] == pytest.approx(5.0)
    assert round(rows[0]["pnl"], 2) == 200.0


# ---------- margin: the thing Issue #3 asked for ----------

def test_a_trade_with_too_little_free_margin_is_refused():
    """1% risk on a 5-pip stop is a huge position. At 1x leverage the margin
    dwarfs the account, so a broker would reject it — and so do we."""
    t = trade(1.10, 1.0995, -0.0005, -1.0)
    rows, summary = simulate([t], initial_balance=10_000, leverage=1.0)
    assert rows[0]["taken"] is False
    assert "margin" in rows[0]["skip_reason"]
    assert summary["trades_skipped"] == 1
    assert summary["final_equity"] == 10_000.0   # untouched — it never opened


def test_leverage_decides_whether_the_same_trade_fits():
    t = trade(1.10, 1.0995, -0.0005, -1.0)
    assert simulate([t], initial_balance=10_000, leverage=1.0)[0][0]["taken"] is False
    assert simulate([t], initial_balance=10_000, leverage=30.0)[0][0]["taken"] is True


def test_margin_is_held_while_open_and_freed_when_the_trade_closes():
    """Two overlapping positions must compete for margin; the same two, one
    after the other, must both fit — because the first released its margin."""
    # Worked out by hand: $100 risk / 0.0005 stop = 200,000 EUR = $220,000 of
    # position. At 30:1 that needs $7,333 margin — fits in $10,000, and leaves
    # only $2,667 free, which the second identical trade cannot have.
    overlapping = [
        trade(1.10, 1.0995, -0.0005, -1.0, entry_date="2024-01-01", exit_date="2024-01-10"),
        trade(1.10, 1.0995, -0.0005, -1.0, entry_date="2024-01-02", exit_date="2024-01-11"),
    ]
    rows, _ = simulate(overlapping, initial_balance=10_000, leverage=30.0)
    assert rows[0]["taken"] is True
    assert rows[0]["margin_required"] == pytest.approx(220_000 / 30, rel=1e-9)
    assert rows[1]["taken"] is False      # first one is still holding the margin

    sequential = [
        trade(1.10, 1.0995, -0.0005, -1.0, entry_date="2024-01-01", exit_date="2024-01-02"),
        trade(1.10, 1.0995, -0.0005, -1.0, entry_date="2024-01-03", exit_date="2024-01-04"),
    ]
    rows2, _ = simulate(sequential, initial_balance=10_000, leverage=30.0)
    assert rows2[0]["taken"] and rows2[1]["taken"]


def test_margin_is_shared_across_pairs():
    """The point of doing this outside the engine: a EURUSD position eats
    margin the gold trade then can't have. A per-pair loop couldn't see it."""
    ts = [
        trade(1.10, 1.0995, -0.0005, -1.0, pair="EURUSD",
              entry_date="2024-01-01", exit_date="2024-01-10"),
        trade(2000.0, 1999.0, -1.0, -1.0, pair="XAUUSD",
              entry_date="2024-01-02", exit_date="2024-01-09"),
    ]
    rows, _ = simulate(ts, initial_balance=10_000, leverage=30.0)
    assert rows[0]["taken"] is True          # EURUSD takes $7,333 of margin
    assert rows[1]["taken"] is False         # gold wants $6,667, only $2,667 left
    assert "free" in rows[1]["skip_reason"]


# ---------- reporting & guards ----------

def test_drawdown_is_measured_in_real_money():
    ts = [trade(1.10, 1.09, -0.01, -1.0, entry_date="2024-01-01", exit_date="2024-01-02"),
          trade(1.10, 1.09, -0.01, -1.0, entry_date="2024-01-03", exit_date="2024-01-04")]
    _, summary = simulate(ts, initial_balance=10_000, risk_per_trade=0.01)
    # -100 then -99 (1% of 9,900)
    assert round(summary["final_equity"], 2) == 9_801.0
    assert round(summary["max_drawdown_usd"], 2) == 199.0
    assert summary["max_drawdown_pct"] == pytest.approx(1.99, abs=0.01)


def test_a_trade_with_no_stop_cannot_be_sized():
    t = trade(1.10, 1.12, 0.02, None)
    rows, summary = simulate([t], initial_balance=10_000)
    assert rows[0]["taken"] is False
    assert "stop distance" in rows[0]["skip_reason"]
    assert summary["trades_skipped"] == 1


def test_bad_account_settings_are_rejected():
    t = trade(1.10, 1.09, -0.01, -1.0)
    with pytest.raises(ValueError, match="initial_balance"):
        simulate([t], initial_balance=0)
    with pytest.raises(ValueError, match="risk_per_trade"):
        simulate([t], risk_per_trade=1.5)
    with pytest.raises(ValueError, match="leverage"):
        simulate([t], leverage=0)


def test_cross_pairs_are_refused_rather_than_guessed():
    from core import pairs
    pairs.PAIRS["EURGBP"] = {"ticker": "EURGBP=X", "pip_size": 0.0001,
                             "color": "#fff", "base": "EUR", "quote": "GBP"}
    try:
        with pytest.raises(ValueError, match="cross pairs|third rate"):
            simulate([trade(0.85, 0.84, -0.01, -1.0, pair="EURGBP")])
    finally:
        del pairs.PAIRS["EURGBP"]
