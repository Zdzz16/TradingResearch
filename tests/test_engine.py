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

# ======================================================================
# Issue #3 — the v3/v4 features that had no committed coverage until now.
# Every expected number below was worked out on paper first.
# ======================================================================

FLAT = (1.0, 1.0, 1.0, 1.0, False)


def frame(rows, start="2024-01-01", freq="D", **extra):
    """rows = list of (open, high, low, close, signal)."""
    idx = pd.date_range(start, periods=len(rows), freq=freq)
    df = pd.DataFrame({
        "Open": [r[0] for r in rows], "High": [r[1] for r in rows],
        "Low": [r[2] for r in rows], "Close": [r[3] for r in rows],
        "NewSignal": [r[4] for r in rows],
    }, index=idx)
    for k, v in extra.items():
        df[k] = v
    df.index.name = "Date"
    return df


# ---------- Task 1: look-ahead bias ----------

def test_no_lookahead_future_bars_cannot_change_a_finished_trade():
    """The strongest proof we can run: a trade that closed on bar 3 must be
    identical whether or not bars 4..N exist. If any decision peeked at
    future data, adding bars would change the answer."""
    import random
    rng = random.Random(4242)

    for scen in range(40):
        rows, prev = [], 1.0
        for _ in range(60):
            o = prev + rng.gauss(0, 0.004)
            c = o + rng.gauss(0, 0.006)
            hi = max(o, c) + abs(rng.gauss(0, 0.003))
            lo = min(o, c) - abs(rng.gauss(0, 0.003))
            rows.append((o, hi, lo, c, rng.random() < 0.15))
            prev = c

        params = dict(stop_loss=0.01, take_profit=0.02, max_hold_days=5,
                      trailing_stop=rng.choice([None, 0.008]),
                      break_even_at=rng.choice([None, 0.006]))
        full = run_backtest(frame(rows), **params)
        cut_at = 30
        short = run_backtest(frame(rows[:cut_at]), **params)

        # every trade the truncated run finished must match the full run's
        # version of that same trade, field for field
        for t in short.itertuples():
            if t.exit_reason == "end_of_data":
                continue  # only that run ran out of data; not comparable
            match = full[full["entry_date"] == t.entry_date]
            assert len(match) == 1, f"scen {scen}: trade vanished when data grew"
            m = match.iloc[0]
            assert m["exit_date"] == t.exit_date, f"scen {scen}: exit moved"
            assert m["exit_reason"] == t.exit_reason, f"scen {scen}: reason changed"
            assert abs(m["exit_price"] - t.exit_price) < 1e-12, f"scen {scen}: fill changed"


def test_entry_never_uses_the_signal_bar_price():
    """A signal on bar 0 must fill at bar 1's OPEN — never bar 0's close,
    which you couldn't have acted on."""
    d = frame([(1.0, 1.5, 0.5, 1.4, True), (1.2345, 1.3, 1.1, 1.2, False), FLAT, FLAT])
    t = run_backtest(d, stop_loss=0.5, take_profit=0.5, max_hold_days=3).iloc[0]
    assert t["entry_price"] == 1.2345
    assert str(t["entry_date"])[:10] == "2024-01-02"


# ---------- Task 4: data gaps ----------

def test_weekend_gaps_do_not_break_logic_or_invent_trades():
    """Real FX data skips weekends (525 such gaps in our EURUSD file). The
    engine counts BARS, not calendar days, so a gap must change nothing."""
    rows = [(1.0, 1.0, 1.0, 1.0, True)] + [FLAT] * 5
    contiguous = run_backtest(frame(rows, freq="D"), stop_loss=0.05,
                              take_profit=0.05, max_hold_days=3)
    # same bars, but the dates jump across a weekend
    gapped = frame(rows, freq="D")
    gapped.index = pd.to_datetime(["2024-01-04", "2024-01-05", "2024-01-08",
                                   "2024-01-09", "2024-01-10", "2024-01-11"])
    gapped.index.name = "Date"
    g = run_backtest(gapped, stop_loss=0.05, take_profit=0.05, max_hold_days=3)

    assert len(contiguous) == len(g) == 1
    assert contiguous.iloc[0]["exit_reason"] == g.iloc[0]["exit_reason"]
    assert contiguous.iloc[0]["days_held"] == g.iloc[0]["days_held"] == 3
    # Entry is bar 1 (Fri 05); holding 3 BARS lands on Tue 09 — Fri, Mon, Tue.
    # The weekend costs no hold time, which is the whole point: the engine
    # counts bars, and a market that isn't open isn't a bar.
    assert str(g.iloc[0]["entry_date"])[:10] == "2024-01-05"
    assert str(g.iloc[0]["exit_date"])[:10] == "2024-01-09"


# ---------- shorts ----------

def test_short_stop_and_target_mirror_the_long_side():
    d = frame([(1.0, 1.0, 1.0, 1.0, True), FLAT, (1.0, 1.0012, 1.0, 1.0008, False), FLAT, FLAT],
              Direction=[-1, None, None, None, None])
    t = run_backtest(d, stop_loss=0.0010, max_hold_days=4).iloc[0]
    assert t["direction"] == "short"
    assert t["exit_reason"] == "stop_loss"
    assert round(t["exit_price"], 6) == 1.0010
    assert round(t["profit"], 6) == -0.0010
    assert round(t["r_multiple"], 6) == -1.0
    assert round(t["mae"], 6) == 0.0012      # worst was 12 pips against

    d2 = frame([(1.0, 1.0, 1.0, 1.0, True), FLAT, (1.0, 1.0, 0.9990, 0.9995, False), FLAT, FLAT],
               Direction=[-1, None, None, None, None])
    t2 = run_backtest(d2, stop_loss=0.05, take_profit=0.0005, max_hold_days=4).iloc[0]
    assert t2["exit_reason"] == "take_profit"
    assert round(t2["profit"], 6) == 0.0005


def test_bad_direction_is_rejected():
    d = frame([(1.0, 1.0, 1.0, 1.0, True), FLAT, FLAT], Direction=[2, None, None])
    with pytest.raises(ValueError, match="Direction"):
        run_backtest(d, stop_loss=0.01)


# ---------- per-signal risk ----------

def test_per_signal_stop_and_target_override_the_defaults():
    d = frame([(1.0, 1.0, 1.0, 1.0, True), FLAT, (1.0, 1.0, 0.9994, 0.9996, False), FLAT, FLAT],
              StopDistance=[0.0005, None, None, None, None])
    t = run_backtest(d, stop_loss=0.05, max_hold_days=4).iloc[0]
    assert round(t["exit_price"], 6) == 0.9995
    assert round(t["r_multiple"], 6) == -1.0   # R uses THIS signal's stop

    d2 = frame([(1.0, 1.0, 1.0, 1.0, True), FLAT, (1.0, 1.0004, 1.0, 1.0002, False), FLAT, FLAT],
               TargetDistance=[0.0003, None, None, None, None])
    t2 = run_backtest(d2, max_hold_days=4).iloc[0]
    assert t2["exit_reason"] == "take_profit" and round(t2["exit_price"], 6) == 1.0003


# ---------- dynamic stops ----------

def test_trailing_stop_follows_the_best_price_and_only_tightens():
    # day2 high 1.0100 lifts the trail to 1.0050 for day3; day3 low 1.0040 hits it.
    d = frame([(1.0, 1.0, 1.0, 1.0, True), FLAT, (1.0, 1.0100, 1.0, 1.0080, False),
               (1.0060, 1.0070, 1.0040, 1.0050, False), FLAT])
    t = run_backtest(d, trailing_stop=0.0050, max_hold_days=5).iloc[0]
    assert t["exit_reason"] == "trailing_stop"
    assert round(t["exit_price"], 6) == 1.0050
    assert round(t["mfe"], 6) == 0.0100


def test_break_even_arms_then_exits_at_entry():
    d = frame([(1.0, 1.0, 1.0, 1.0, True), FLAT, (1.0, 1.0040, 1.0, 1.0030, False),
               (1.0005, 1.0010, 0.9995, 1.0, False), FLAT, FLAT])
    t = run_backtest(d, stop_loss=0.0100, break_even_at=0.0030, max_hold_days=6).iloc[0]
    assert t["exit_reason"] == "break_even"
    assert round(t["exit_price"], 6) == 1.0
    assert round(t["profit"], 6) == 0.0


# ---------- limit entries ----------

def test_limit_entry_fills_at_the_limit_or_better_and_expires():
    d = frame([(1.0, 1.0, 1.0, 1.0, True), (1.0, 1.0, 0.9990, 1.0, False),
               (1.0, 1.0, 0.9975, 0.9985, False), FLAT, FLAT, FLAT],
              EntryLimit=[0.9980, None, None, None, None, None])
    t = run_backtest(d, max_hold_days=3)
    assert len(t) == 1 and round(t.iloc[0]["entry_price"], 6) == 0.9980
    assert t.iloc[0]["entry_type"] == "limit"

    # gapping through the limit fills at the (better) open
    d2 = frame([(1.0, 1.0, 1.0, 1.0, True), (0.9970, 0.9975, 0.9965, 0.9970, False), FLAT, FLAT],
               EntryLimit=[0.9980, None, None, None])
    assert round(run_backtest(d2, max_hold_days=3).iloc[0]["entry_price"], 6) == 0.9970

    # never touched -> expires -> no trade
    d3 = frame([(1.0, 1.0, 1.0, 1.0, True), FLAT, FLAT, FLAT, FLAT],
               EntryLimit=[0.9980, None, None, None, None])
    assert len(run_backtest(d3, max_hold_days=3, entry_valid_days=2)) == 0


def test_fill_bar_target_is_not_trusted_on_a_mid_bar_limit_fill():
    """The bar's high may have happened BEFORE our limit filled, so a target
    hit on the fill bar can't be proven — but the stop can (price had to pass
    the limit to reach it)."""
    d = frame([(1.0, 1.0, 1.0, 1.0, True), (1.0, 1.0010, 0.9975, 1.0, False),
               (1.0, 1.0005, 0.9995, 1.0, False), FLAT, FLAT],
              EntryLimit=[0.9980, None, None, None, None])
    t = run_backtest(d, take_profit=0.0020, max_hold_days=4).iloc[0]
    assert str(t["exit_date"])[:10] == "2024-01-03"   # taken the NEXT bar, not the fill bar

    d2 = frame([(1.0, 1.0, 1.0, 1.0, True), (1.0, 1.0010, 0.9950, 0.9960, False), FLAT, FLAT],
               EntryLimit=[0.9980, None, None, None])
    t2 = run_backtest(d2, stop_loss=0.0020, max_hold_days=4).iloc[0]
    assert t2["exit_reason"] == "stop_loss"          # the stop IS trusted


# ---------- exit signals ----------

def test_exit_signal_closes_at_the_next_open():
    d = frame([(1.0, 1.0, 1.0, 1.0, True), FLAT, FLAT,
               (1.0030, 1.0035, 1.0028, 1.0032, False), FLAT])
    d["ExitSignal"] = [False, False, True, False, False]
    t = run_backtest(d, max_hold_days=5).iloc[0]
    assert t["exit_reason"] == "exit_signal"
    assert round(t["exit_price"], 6) == 1.0030      # next bar's open, not this close


# ---------- position cap ----------

def test_max_open_trades_caps_concurrency():
    rows = [(1.0, 1.0, 1.0, 1.0, True)] * 3 + [FLAT] * 5
    d = frame(rows)
    assert len(run_backtest(d, max_hold_days=5, max_open_trades=2)) == 2
    assert len(run_backtest(d, max_hold_days=5, max_open_trades=3)) == 3
    assert len(run_backtest(d, max_hold_days=5)) == 1               # default = 1


# ---------- ambiguity ----------

def test_ambiguous_bar_is_flagged_and_bounded_by_policy():
    """One bar holds both levels; daily data can't say which came first."""
    d = frame([(1.0, 1.0, 1.0, 1.0, True), FLAT, (1.0, 1.0010, 0.9985, 1.0, False), FLAT, FLAT])
    pess = run_backtest(d, stop_loss=0.0010, take_profit=0.0005, max_hold_days=3).iloc[0]
    opt = run_backtest(d, stop_loss=0.0010, take_profit=0.0005, max_hold_days=3,
                       ambiguous_policy="target").iloc[0]
    assert pess["exit_reason"] == "stop_loss" and bool(pess["ambiguous"])
    assert opt["exit_reason"] == "take_profit" and bool(opt["ambiguous"])
    assert opt["profit"] > pess["profit"]   # the truth lies between the two


# ---------- costs ----------

def test_slippage_worsens_stops_but_never_limit_fills():
    d = frame([(1.0, 1.0, 1.0, 1.0, True), FLAT, (1.0, 1.0, 0.9985, 0.9990, False), FLAT, FLAT])
    t = run_backtest(d, stop_loss=0.0010, max_hold_days=4, slippage=0.0002).iloc[0]
    assert round(t["exit_price"], 6) == 0.9988    # 2 pips worse than the stop

    d2 = frame([(1.0, 1.0, 1.0, 1.0, True), FLAT, (1.0, 1.0005, 1.0, 1.0, False), FLAT, FLAT])
    t2 = run_backtest(d2, stop_loss=0.05, take_profit=0.0005, max_hold_days=4,
                      slippage=0.0002).iloc[0]
    assert round(t2["exit_price"], 6) == 1.0005  # a limit order fills at its price


def test_swap_is_charged_per_night_and_can_be_earned():
    d = frame([(1.0, 1.0, 1.0, 1.0, True), FLAT, FLAT, FLAT, FLAT])
    t = run_backtest(d, max_hold_days=3, swap_per_night=0.0001).iloc[0]
    assert round(t["profit"], 6) == -0.0002 and t["days_held"] == 3   # 3 bars = 2 nights
    t2 = run_backtest(d, max_hold_days=3, swap_per_night=-0.0001).iloc[0]
    assert round(t2["profit"], 6) == 0.0002                            # negative = carry earned

    # entered and stopped the same bar = zero nights
    d3 = frame([(1.0, 1.0, 1.0, 1.0, True), (1.0, 1.0, 0.9985, 0.9990, False), FLAT, FLAT])
    t3 = run_backtest(d3, stop_loss=0.0010, max_hold_days=3, swap_per_night=0.0001).iloc[0]
    assert round(t3["profit"], 6) == -0.0010 and t3["days_held"] == 1


def test_commission_is_charged_on_entry_notional():
    d = frame([(1.0, 1.0, 1.0, 1.0, True), FLAT, (1.0, 1.0005, 1.0, 1.0, False), FLAT, FLAT])
    t = run_backtest(d, take_profit=0.0005, max_hold_days=3, commission_pct=0.0002).iloc[0]
    assert round(t["profit"], 6) == 0.0003     # +0.0005 gross - 0.0002 commission


# ---------- data hygiene ----------

def test_envelope_rule_trusts_every_reported_price():
    """Yahoo reports Opens/Closes outside the High-Low range (30-82 bars per
    pair). A close below the low still traded, so the stop must trigger."""
    d = frame([(1.0, 1.0, 1.0, 1.0, True), FLAT, (1.0, 1.0, 0.9990, 0.9985, False), FLAT, FLAT])
    t = run_backtest(d, stop_loss=0.0011, max_hold_days=4).iloc[0]
    assert t["exit_reason"] == "stop_loss" and round(t["exit_price"], 6) == 0.9989


def test_truly_corrupt_bar_is_rejected():
    d = frame([(1.0, 1.0, 1.0, 1.0, True), FLAT, (1.0, 0.9980, 0.9990, 0.9985, False), FLAT])
    with pytest.raises(ValueError, match="High < Low"):
        run_backtest(d, stop_loss=0.01)
