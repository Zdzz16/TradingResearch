def summarize(trades):
    """
    Prints key performance stats for a set of backtested trades.
    trades: a DataFrame like the one returned by run_backtest()
    """
    total = len(trades)
    if total == 0:
        print("No trades to summarize.")
        return

    wins = trades[trades["profit"] > 0]
    losses = trades[trades["profit"] <= 0]

    win_rate = len(wins) / total * 100
    avg_win = wins["profit"].mean() if len(wins) > 0 else 0
    avg_loss = losses["profit"].mean() if len(losses) > 0 else 0
    total_profit = trades["profit"].sum()

    print(f"Total trades: {total}")
    print(f"Win rate: {win_rate:.1f}%")
    print(f"Average win: {avg_win:.5f}")
    print(f"Average loss: {avg_loss:.5f}")
    print(f"Total profit: {total_profit:.5f}")

    print("\nExit reason breakdown:")
    print(trades["exit_reason"].value_counts())