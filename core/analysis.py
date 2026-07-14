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

    print(f"--- {label} ---")
    print(f"Total trades: {stats['total_trades']}")
    print(f"Win rate: {stats['win_rate']}%")
    print(f"Average win: {stats['avg_win']}")
    print(f"Average loss: {stats['avg_loss']}")
    print(f"Total profit: {stats['total_profit']}")
    print("\nExit reason breakdown:")
    print(trades["exit_reason"].value_counts())

    return stats