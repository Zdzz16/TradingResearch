def summarize(trades, label="Strategy", print_output=True):
    """
    Calculates key performance stats for a set of backtested trades.
    Returns a dict of the stats (so results can be compared, stored, or
    fed into a dashboard later) and optionally prints a readable summary.

    label: a name for this run, useful once we're comparing multiple
           strategies side by side.
    print_output: set False if you just want the dict without terminal noise
                  (e.g. when running many strategies in a loop).
    """
    total = len(trades)
    if total == 0:
        stats = {"label": label, "total_trades": 0}
        if print_output:
            print(f"{label}: No trades to summarize.")
        return stats

    wins = trades[trades["profit"] > 0]
    losses = trades[trades["profit"] <= 0]

    win_rate = len(wins) / total * 100
    avg_win = wins["profit"].mean() if len(wins) > 0 else 0
    avg_loss = losses["profit"].mean() if len(losses) > 0 else 0
    total_profit = trades["profit"].sum()

    # Expectancy: the average amount you'd expect to make (or lose) per
    # trade, blending win rate and win/loss size into one number. This is
    # usually more meaningful than win rate alone — a strategy can win
    # less than half the time and still have positive expectancy, if wins
    # are big enough relative to losses.
    expectancy = (win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss)

    # Max drawdown: the single worst peak-to-trough drop in cumulative
    # profit across the whole sequence — i.e. the worst losing stretch
    # you'd have had to sit through, in order.
    equity = trades["profit"].cumsum()
    running_max = equity.cummax()
    drawdown = equity - running_max
    max_drawdown = drawdown.min()

    stats = {
        "label": label,
        "total_trades": total,
        "win_rate": round(win_rate, 1),
        "avg_win": round(avg_win, 5),
        "avg_loss": round(avg_loss, 5),
        "total_profit": round(total_profit, 5),
        "expectancy": round(expectancy, 5),
        "max_drawdown": round(max_drawdown, 5),
    }

    if print_output:
        print(f"--- {label} ---")
        print(f"Total trades: {stats['total_trades']}")
        print(f"Win rate: {stats['win_rate']}%")
        print(f"Average win: {stats['avg_win']}")
        print(f"Average loss: {stats['avg_loss']}")
        print(f"Total profit: {stats['total_profit']}")
        print(f"Expectancy per trade: {stats['expectancy']}")
        print(f"Max drawdown: {stats['max_drawdown']}")
        print("\nExit reason breakdown:")
        print(trades["exit_reason"].value_counts())

    return stats