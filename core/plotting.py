import matplotlib.pyplot as plt

from core.pairs import PAIRS

def plot_equity_curve(trades, title="Equity Curve"):
    trades = trades.copy()
    trades["equity"] = trades["profit"].cumsum()

    plt.figure(figsize=(10, 5))
    plt.plot(trades["equity"], color="blue")
    plt.axhline(0, color="gray", linestyle="--")
    plt.title(title)
    plt.xlabel("Trade number")
    plt.ylabel("Cumulative profit (price units)")
    plt.grid(True, alpha=0.3)
    plt.show()

def plot_pair_comparison(trades_by_pair, title="Equity Curves by Pair"):
    """
    Draws every pair's equity curve on ONE chart, each in the fixed color
    assigned to it in core/pairs.py — so a pair looks the same in every
    chart, every run (and later, the dashboard).

    Curves are in cumulative R (profit in units of risk) instead of raw
    price units, because price units aren't comparable across instruments:
    gold's $20 swings would visually bury EURUSD's 0.01s.

    trades_by_pair: dict like {"EURUSD": trades_dataframe, ...}
    """
    plt.figure(figsize=(10, 5))
    for pair_name, trades in trades_by_pair.items():
        if len(trades) == 0:
            continue
        equity_r = trades["r_multiple"].cumsum()
        color = PAIRS.get(pair_name, {}).get("color")
        plt.plot(equity_r.values, color=color, label=pair_name)
    plt.axhline(0, color="gray", linestyle="--")
    plt.title(title)
    plt.xlabel("Trade number")
    plt.ylabel("Cumulative R (multiples of risk)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.show()