def summarize(trades, label="Strategy", verbose=True):
    """
    Calculates key performance stats for a set of backtested trades.
    Returns the stats as a dictionary; with verbose=True (the default,
    right for command-line runs) it also prints a readable summary.
    The dashboard passes verbose=False — otherwise every API call would
    spam the server console.

    label: a name for this run, useful when comparing runs.
    """
    total = len(trades)
    if total == 0:
        if verbose:
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

        # Average win/loss in R (comparable across pairs), and the win rate
        # this strategy must beat just to break even given how big its wins
        # and losses actually turned out. THIS is what makes a win rate good
        # or bad — not a fixed threshold: win 39% with 2:1 winners and you
        # make money; win 55% with 1:2 winners and you don't.
        wins_r = trades.loc[trades["profit"] > 0, "r_multiple"]
        losses_r = trades.loc[trades["profit"] <= 0, "r_multiple"]
        avg_win_r = float(wins_r.mean()) if len(wins_r) else 0.0
        avg_loss_r = float(losses_r.mean()) if len(losses_r) else 0.0  # negative
        stats["avg_win_r"] = round(avg_win_r, 3)
        stats["avg_loss_r"] = round(avg_loss_r, 3)
        span = avg_win_r + abs(avg_loss_r)
        stats["breakeven_win_rate"] = (
            round(abs(avg_loss_r) / span * 100, 1) if span else None
        )

    # How many exits leaned on the engine's pessimistic same-bar
    # assumption (stop and target both inside one bar, order unknowable).
    # If this is a big share of all trades, get finer-grained data before
    # trusting the numbers.
    if "ambiguous" in trades.columns:
        stats["ambiguous_exits"] = int(trades["ambiguous"].sum())

    if verbose:
        print(f"--- {label} ---")
        print(f"Total trades: {stats['total_trades']}")
        print(f"Win rate: {stats['win_rate']}%")
        print(f"Average win: {stats['avg_win']}")
        print(f"Average loss: {stats['avg_loss']}")
        print(f"Total profit: {stats['total_profit']}")
        if "total_r" in stats:
            print(f"Total R: {stats['total_r']} (expectancy: {stats['expectancy_r']}R per trade)")
            print(f"Max drawdown: {stats['max_drawdown_r']}R")
            print(f"Break-even win rate: {stats['breakeven_win_rate']}%")
        if stats.get("ambiguous_exits"):
            print(f"Ambiguous exits: {stats['ambiguous_exits']} "
                  "(stop+target in one bar — engine assumed the stop)")
        print("\nExit reason breakdown:")
        print(trades["exit_reason"].value_counts())

    return stats
