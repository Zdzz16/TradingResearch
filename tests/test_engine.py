import pandas as pd
import pytest
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

def test_r_multiple_and_return_pct_columns():
    """
    The stop-loss scenario risks 0.0010 and loses exactly that, so
    r_multiple must be -1.0 ("lost 1x what I risked"). return_pct is
    profit divided by the entry price: -0.0010 / 1.0000.
    """
    data = make_fake_data()
    trades = run_backtest(data, stop_loss=0.0010, take_profit=None, max_hold_days=3)

    trade = trades.iloc[0]
    assert round(trade["r_multiple"], 6) == -1.0
    assert round(trade["return_pct"], 6) == round(-0.0010 / 1.0000, 6)

def test_r_multiple_is_empty_without_a_stop():
    """No stop_loss means there's no 'risk unit' to measure in — the
    r_multiple column must then be empty (NaN), not some made-up number."""
    data = make_fake_data()
    trades = run_backtest(data, stop_loss=None, take_profit=None, max_hold_days=3)

    assert trades["r_multiple"].isna().all()

def test_same_bar_stop_and_target_assumes_stop_and_flags_ambiguous():
    """
    Day 2's range contains BOTH the stop (0.9990) and the target (1.0005).
    Daily data can't tell which was touched first, so the engine must take
    the pessimistic route (the stop) — and be honest about it by setting
    ambiguous=True on that trade.
    """
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    data = pd.DataFrame({
        "Open":  [1.0000, 1.0000, 1.0000, 1.0000, 1.0000],
        "High":  [1.0000, 1.0000, 1.0010, 1.0000, 1.0000],  # above target
        "Low":   [1.0000, 1.0000, 0.9985, 1.0000, 1.0000],  # below stop
        "Close": [1.0000, 1.0000, 1.0000, 1.0000, 1.0000],
        "NewSignal": [True, False, False, False, False],
    }, index=dates)
    data.index.name = "Date"

    trades = run_backtest(data, stop_loss=0.0010, take_profit=0.0005, max_hold_days=3)

    trade = trades.iloc[0]
    assert trade["exit_reason"] == "stop_loss"
    assert trade["ambiguous"] == True
    assert round(trade["exit_price"], 4) == 0.9990

def test_plain_exits_are_not_flagged_ambiguous():
    """An ordinary stop-out (target never touched) must NOT be flagged."""
    data = make_fake_data()
    trades = run_backtest(data, stop_loss=0.0010, take_profit=None, max_hold_days=3)

    assert not trades["ambiguous"].any()

def test_gap_open_beyond_target_beats_intrabar_stop():
    """
    Day 2 OPENS at 1.0010 — already past the 1.0005 target — so the trade
    was closed (in profit, at the open) before the day's later slide down
    through the stop could matter. The old ordering would have wrongly
    recorded a stop-out here.
    """
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    data = pd.DataFrame({
        "Open":  [1.0000, 1.0000, 1.0010, 1.0000, 1.0000],  # gap up past target
        "High":  [1.0000, 1.0000, 1.0012, 1.0000, 1.0000],
        "Low":   [1.0000, 1.0000, 0.9985, 1.0000, 1.0000],  # later crosses the stop
        "Close": [1.0000, 1.0000, 0.9990, 1.0000, 1.0000],
        "NewSignal": [True, False, False, False, False],
    }, index=dates)
    data.index.name = "Date"

    trades = run_backtest(data, stop_loss=0.0010, take_profit=0.0005, max_hold_days=3)

    trade = trades.iloc[0]
    assert trade["exit_reason"] == "take_profit"
    assert round(trade["exit_price"], 4) == 1.0010  # the (better) gap open
    assert trade["ambiguous"] == False  # an open fill is not a guess

def test_trade_cut_off_by_data_end_is_labeled_end_of_data():
    """
    Signal on day 3 -> entry on day 4, the LAST bar we have. The trade
    never got its full window, so calling it a 'time_exit' would be a lie —
    it must be labeled 'end_of_data'.
    """
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    data = pd.DataFrame({
        "Open":  [1.0] * 5,
        "High":  [1.0] * 5,
        "Low":   [1.0] * 5,
        "Close": [1.0] * 5,
        "NewSignal": [False, False, False, True, False],
    }, index=dates)
    data.index.name = "Date"

    trades = run_backtest(data, stop_loss=0.05, take_profit=0.05, max_hold_days=3)

    assert len(trades) == 1
    assert trades.iloc[0]["exit_reason"] == "end_of_data"

def test_nan_prices_are_rejected():
    """A NaN price would silently disable stop/target checks for that bar
    (NaN comparisons are always False) — the engine must refuse loudly."""
    data = make_fake_data()
    data.loc[data.index[2], "High"] = None

    with pytest.raises(ValueError, match="missing OHLC"):
        run_backtest(data, stop_loss=0.0010, max_hold_days=3)

def test_missing_required_column_is_rejected():
    data = make_fake_data().drop(columns=["NewSignal"])

    with pytest.raises(ValueError, match="NewSignal"):
        run_backtest(data, stop_loss=0.0010, max_hold_days=3)

def test_spread_is_deducted_from_every_trade():
    """
    Take-profit trade: gross +0.0005, spread 0.0002 -> net profit +0.0003.
    return_pct and r_multiple must be computed from the NET number — the
    spread is a real cost, so every stat downstream should feel it.
    """
    data = make_fake_data()
    trades = run_backtest(data, stop_loss=0.05, take_profit=0.0005,
                          max_hold_days=3, spread=0.0002)

    trade = trades.iloc[0]
    assert trade["exit_reason"] == "take_profit"
    assert round(trade["profit"], 6) == 0.0003
    assert round(trade["return_pct"], 6) == 0.0003
    assert round(trade["r_multiple"], 6) == round(0.0003 / 0.05, 6)