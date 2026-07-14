def summarize(trades, label="Strategy"):
    """
    Calculates key performance stats for a set of backtested trades.
    Prints a readable summary AND returns the stats as a dictionary,
    so other code (comparisons, dashboards) can use the numbers directly
    instead of re-parsing printed text.

    label: a name for this run, useful once we're comparing multiple
           strategies and need to tell their results apart.
    """
    total = len(trades)
    if total == 0:
        print(f"[{label}] No trades to summarize.")
        return {"label": label, "total_trades": 0}

    wins = trades[trades["profit"] > 0]
    losses = trades[trades["profit"] <= 0]

    win_rate = len(wins) / total * 100
    avg_win = wins["profit"].mean() if len(wins) > 0 else 0
    avg_loss = losses["profit"].mean() if len(losses) > 0 else 0
    total_profit = trades["profit"].sum()

    stats = {
        "label": label,
        "total_trades": total,
        "win_rate": round(win_rate, 1),
        "avg_win": round(avg_win, 5),
        "avg_loss": round(avg_loss, 5),
        "total_profit": round(total_profit, 5),
    }

    # R-multiples measure each trade in units of risk (1R = the stop
    # distance), which IS comparable across pairs — unlike price units,
    # where gold's numbers would dwarf EURUSD's without meaning more.
    if "r_multiple" in trades.columns and trades["r_multiple"].notna().any():
        stats["total_r"] = round(trades["r_multiple"].sum(), 2)
        stats["expectancy_r"] = round(trades["r_multiple"].mean(), 3)

        # Max drawdown: the deepest peak-to-valley dip of the running
        # equity (in R). The number that tells you how bad the worst
        # stretch felt — total profit alone hides it. clip(lower=0)
        # treats the starting balance as the first peak.
        equity = trades["r_multiple"].cumsum()
        stats["max_drawdown_r"] = round(float((equity.cummax().clip(lower=0) - equity).max()), 2)

    # How many exits leaned on the engine's pessimistic same-bar
    # assumption (stop and target both inside one bar, order unknowable).
    # If this is a big share of all trades, get finer-grained data before
    # trusting the numbers.
    if "ambiguous" in trades.columns:
        stats["ambiguous_exits"] = int(trades["ambiguous"].sum())

    print(f"--- {label} ---")
    print(f"Total trades: {stats['total_trades']}")
    print(f"Win rate: {stats['win_rate']}%")
    print(f"Average win: {stats['avg_win']}")
    print(f"Average loss: {stats['avg_loss']}")
    print(f"Total profit: {stats['total_profit']}")
    if "total_r" in stats:
        print(f"Total R: {stats['total_r']} (expectancy: {stats['expectancy_r']}R per trade)")
        print(f"Max drawdown: {stats['max_drawdown_r']}R")
    if stats.get("ambiguous_exits"):
        print(f"Ambiguous exits: {stats['ambiguous_exits']} "
              "(stop+target in one bar — engine assumed the stop)")
    print("\nExit reason breakdown:")
    print(trades["exit_reason"].value_counts())

    return stats