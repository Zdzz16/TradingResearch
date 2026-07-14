import pandas as pd
from core.engine import run_backtest

def make_fake_data():
    """
    A tiny, made-up 5-day price history where WE decide exactly what
    happens each day — so we can check the engine's math against an
    answer we already know is correct, instead of trusting it blindly.
    """
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    data = pd.DataFrame({
        "Open":  [1.0000, 1.0000, 1.0000, 1.0000, 1.0000],
        "High":  [1.0000, 1.0000, 1.0005, 1.0000, 1.0000],
        "Low":   [1.0000, 1.0000, 0.9985, 1.0000, 1.0000],
        "Close": [1.0000, 1.0000, 0.9990, 1.0000, 1.0000],
        "NewSignal": [True, False, False, False, False],
    }, index=dates)
    data.index.name = "Date"
    return data

def test_stop_loss_triggers():
    """
    Signal on day 0 -> we enter day 1 at Open = 1.0000.
    stop_loss = 0.0010, so the stop level is 1.0000 - 0.0010 = 0.9990.
    Day 2's Low is 0.9985, which is BELOW that -> the stop should trigger.
    """
    data = make_fake_data()
    trades = run_backtest(data, stop_loss=0.0010, take_profit=None, max_hold_days=3)

    assert len(trades) == 1, "Expected exactly one trade"
    trade = trades.iloc[0]
    assert trade["exit_reason"] == "stop_loss"
    assert round(trade["exit_price"], 4) == 0.9990

def test_take_profit_triggers():
    """
    Same entry. take_profit = 0.0005, so the target is 1.0000 + 0.0005 = 1.0005.
    Day 2's High is exactly 1.0005 -> take_profit should trigger.
    Stop is set far away on purpose so it can't interfere with this test.
    """
    data = make_fake_data()
    trades = run_backtest(data, stop_loss=0.05, take_profit=0.0005, max_hold_days=3)

    assert len(trades) == 1
    trade = trades.iloc[0]
    assert trade["exit_reason"] == "take_profit"
    assert round(trade["exit_price"], 4) == 1.0005

def test_time_exit_when_nothing_hit():
    """
    Stop and target both set far away, so neither can trigger.
    The trade should just close at max_hold_days on the Close price.
    """
    data = make_fake_data()
    trades = run_backtest(data, stop_loss=0.05, take_profit=0.05, max_hold_days=3)

    assert len(trades) == 1
    assert trades.iloc[0]["exit_reason"] == "time_exit"
def test_stop_loss_triggers_on_entry_day():
    """
    Same setup, but this time the crash happens on the ENTRY day itself
    (day 1, not day 2). The old buggy version would have missed this
    completely, since it only started checking the day AFTER entry.
    """
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    data = pd.DataFrame({
        "Open":  [1.0000, 1.0000, 1.0000, 1.0000, 1.0000],
        "High":  [1.0000, 1.0000, 1.0000, 1.0000, 1.0000],
        "Low":   [1.0000, 0.9985, 1.0000, 1.0000, 1.0000],  # crash on entry day
        "Close": [1.0000, 0.9990, 1.0000, 1.0000, 1.0000],
        "NewSignal": [True, False, False, False, False],
    }, index=dates)
    data.index.name = "Date"

    trades = run_backtest(data, stop_loss=0.0010, take_profit=None, max_hold_days=3)

    assert len(trades) == 1
    assert trades.iloc[0]["exit_reason"] == "stop_loss"
def test_overlapping_signals_are_skipped_by_default():
    """
    Two signals fire close together — day 0 and day 1. The first trade
    (entered day 1) won't close until day 3 (time exit, max_hold_days=3).
    The second signal would enter on day 2, which is BEFORE the first
    trade closes — so it should be skipped entirely by default.
    """
    dates = pd.date_range("2024-01-01", periods=6, freq="D")
    data = pd.DataFrame({
        "Open":  [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
        "High":  [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
        "Low":   [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
        "Close": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
        "NewSignal": [True, True, False, False, False, False],
    }, index=dates)
    data.index.name = "Date"

    trades = run_backtest(data, stop_loss=0.05, take_profit=0.05, max_hold_days=3)

    assert len(trades) == 1, "Second overlapping signal should have been skipped"

def test_allow_overlap_true_permits_both():
    """Same data, but explicitly allowing overlap should let both trades through."""
    dates = pd.date_range("2024-01-01", periods=6, freq="D")
    data = pd.DataFrame({
        "Open":  [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
        "High":  [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
        "Low":   [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
        "Close": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
        "NewSignal": [True, True, False, False, False, False],
    }, index=dates)
    data.index.name = "Date"

    trades = run_backtest(data, stop_loss=0.05, take_profit=0.05, max_hold_days=3, allow_overlap=True)

    assert len(trades) == 2, "Both signals should produce trades when overlap is allowed"
def test_stop_loss_fills_at_gap_open_not_theoretical_price():
    """
    Entry at 1.0000, stop_loss = 0.0010 -> stop level = 0.9990.
    On day 2, the market GAPS DOWN — it opens already at 0.9950,
    well below our stop level, before ever trading at 0.9990.
    A realistic engine must fill at that worse Open price (0.9950),
    NOT pretend we magically got out at our neat 0.9990 stop level.
    """
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    data = pd.DataFrame({
        "Open":  [1.0000, 1.0000, 0.9950, 1.0000, 1.0000],  # gap down on day 2
        "High":  [1.0000, 1.0000, 0.9955, 1.0000, 1.0000],
        "Low":   [1.0000, 1.0000, 0.9940, 1.0000, 1.0000],
        "Close": [1.0000, 1.0000, 0.9950, 1.0000, 1.0000],
        "NewSignal": [True, False, False, False, False],
    }, index=dates)
    data.index.name = "Date"

    trades = run_backtest(data, stop_loss=0.0010, take_profit=None, max_hold_days=3)

    assert len(trades) == 1
    assert trades.iloc[0]["exit_reason"] == "stop_loss"
    assert round(trades.iloc[0]["exit_price"], 4) == 0.9950  # the gap price, not 0.9990