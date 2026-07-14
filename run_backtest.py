import pandas as pd

from core.data_loader import get_data
from core.strategies import ma_crossover
from core.engine import run_backtest
from core.analysis import summarize
from core.plotting import plot_pair_comparison
from core.pairs import PAIRS, get_pair, pips_to_price, DEFAULT_SL_PIPS, DEFAULT_TP_PIPS

START, END = "2015-01-01", "2024-12-31"


def run_strategy(pair_name, sl_pips=None, tp_pips=None, window=20, max_hold_days=10,
                 start=START, end=END):
    """
    Runs the full pipeline for ONE pair: data -> signals -> backtest -> stats.

    sl_pips / tp_pips are in PIPS — they get converted to this pair's price
    units right here, so the engine never needs to know which instrument
    it's testing. Leave them as None to use the pair's own override from
    core/pairs.py (gold has one), or the global defaults otherwise.

    Returns (trades, stats). This function is deliberately the one entry
    point for a single backtest — the future dashboard will call it too,
    so the dashboard and the command line can never drift apart.
    """
    pair = get_pair(pair_name)
    if sl_pips is None:
        sl_pips = pair.get("sl_pips", DEFAULT_SL_PIPS)
    if tp_pips is None:
        tp_pips = pair.get("tp_pips", DEFAULT_TP_PIPS)

    data = get_data(pair["ticker"], start, end)
    data = ma_crossover(data, window=window)

    trades = run_backtest(
        data,
        stop_loss=pips_to_price(pair_name, sl_pips),
        take_profit=pips_to_price(pair_name, tp_pips),
        max_hold_days=max_hold_days,
    )

    # Filename carries the pair and parameters, so runs stop overwriting
    # each other and you can always tell which settings produced a file.
    trades.to_csv(f"results/{pair_name}_ma{window}_sl{sl_pips}_tp{tp_pips}.csv", index=False)

    stats = summarize(trades, label=pair_name)
    return trades, stats


def main():
    all_trades = {}
    all_stats = []

    for pair_name in PAIRS:
        trades, stats = run_strategy(pair_name)
        all_trades[pair_name] = trades
        all_stats.append(stats)
        print()

    # One table with every pair side by side. The R columns are the fair
    # ones to compare — price-unit columns mean something different per
    # pair (see core/pairs.py for why).
    comparison = pd.DataFrame(all_stats).set_index("label")
    print("=== Pair comparison ===")
    print(comparison.to_string())

    plot_pair_comparison(all_trades)


if __name__ == "__main__":
    main()
