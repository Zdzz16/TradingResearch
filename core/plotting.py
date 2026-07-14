import matplotlib.pyplot as plt

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