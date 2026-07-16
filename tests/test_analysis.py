import pandas as pd

from core.analysis import summarize


def frame(r_multiples, stop=0.01):
    """Trades whose profit is consistent with their R (profit = R x stop),
    so win_rate (by profit sign) and the R stats line up."""
    return pd.DataFrame({
        "profit": [r * stop for r in r_multiples],
        "r_multiple": r_multiples,
        "exit_reason": ["take_profit" if r > 0 else "stop_loss" for r in r_multiples],
        "ambiguous": [False] * len(r_multiples),
    })


# ---------- the headline numbers, hand-computed ----------

def test_win_rate_counts_profit_sign():
    s = summarize(frame([2, -1, 2, -1, -1]), verbose=False)
    assert s["total_trades"] == 5
    assert s["win_rate"] == 40.0                 # 2 of 5


def test_expectancy_and_total_r():
    s = summarize(frame([2, -1, 2, -1, -1]), verbose=False)
    assert s["total_r"] == 1.0                    # 2-1+2-1-1
    assert s["expectancy_r"] == 0.2               # 1 / 5


def test_avg_win_and_loss_in_R():
    s = summarize(frame([2, -1, 2, -1, -1]), verbose=False)
    assert s["avg_win_r"] == 2.0                   # (2+2)/2
    assert s["avg_loss_r"] == -1.0                 # (-1-1-1)/3


def test_avg_win_and_loss_in_price_units():
    s = summarize(frame([2, -1, 2, -1, -1], stop=0.01), verbose=False)
    assert s["avg_win"] == 0.02
    assert s["avg_loss"] == -0.01
    assert round(s["total_profit"], 5) == 0.01


def test_breakeven_win_rate_from_realised_payoff():
    # wins avg +2R, losses avg -1R  ->  need |loss| / (win+|loss|) = 1/3
    s = summarize(frame([2, -1, 2, -1, -1]), verbose=False)
    assert s["breakeven_win_rate"] == 33.3


def test_break_even_is_zero_when_you_never_lose():
    s = summarize(frame([2, 1, 3]), verbose=False)
    assert s["breakeven_win_rate"] == 0.0
    assert s["win_rate"] == 100.0


def test_max_drawdown_is_deepest_peak_to_valley_in_R():
    # equity: 2,1,3,2,1  peak: 2,2,3,3,3  dd: 0,1,0,1,2  -> 2
    s = summarize(frame([2, -1, 2, -1, -1]), verbose=False)
    assert s["max_drawdown_r"] == 2.0


def test_a_losing_first_trade_draws_down_from_the_starting_balance():
    # equity starts at 0; first trade -1 -> already 1R underwater
    s = summarize(frame([-1, 1]), verbose=False)
    assert s["max_drawdown_r"] == 1.0


# ---------- edges ----------

def test_no_trades_returns_a_minimal_dict():
    s = summarize(pd.DataFrame(), verbose=False)
    assert s == {"label": "Strategy", "total_trades": 0}


def test_a_break_even_trade_is_not_a_win():
    # profit exactly 0 counts as a loss for win rate (a scratch isn't a win)
    s = summarize(frame([1, 0, 1]), verbose=False)
    assert s["total_trades"] == 3
    assert s["win_rate"] == round(2 / 3 * 100, 1)


def test_r_stats_are_omitted_without_an_r_multiple_column():
    plain = pd.DataFrame({"profit": [0.01, -0.01], "exit_reason": ["take_profit", "stop_loss"]})
    s = summarize(plain, verbose=False)
    assert "total_r" not in s and "breakeven_win_rate" not in s
    assert s["win_rate"] == 50.0


def test_ambiguous_exits_are_counted():
    df = frame([2, -1, -1])
    df.loc[1, "ambiguous"] = True
    s = summarize(df, verbose=False)
    assert s["ambiguous_exits"] == 1


def test_verbose_false_prints_nothing(capsys):
    summarize(frame([1, -1]), verbose=False)
    assert capsys.readouterr().out == ""


def test_verbose_true_prints_a_summary(capsys):
    summarize(frame([1, -1]), label="MyRun", verbose=True)
    out = capsys.readouterr().out
    assert "MyRun" in out and "Win rate" in out
