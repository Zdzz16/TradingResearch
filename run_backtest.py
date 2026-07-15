from pathlib import Path

import pandas as pd

from core.data_loader import get_data
from core.strategies import apply_strategy, strategy_slug
from core.engine import run_backtest
from core.analysis import summarize
from core.plotting import plot_pair_comparison
from core.pairs import PAIRS, get_pair, pips_to_price, DEFAULT_SL_PIPS, DEFAULT_TP_PIPS

START, END = "2015-01-01", "2024-12-31"

# Anchored to the project root, not the working directory — a CLI run from
# another folder used to scatter results wherever it was launched from.
RESULTS_DIR = Path(__file__).resolve().parent / "results"


def run_strategy(pair_name, sl_pips=None, tp_pips=None, spread_pips=None,
                 strategy="ma_crossover", params=None, max_hold_days=10,
                 start=START, end=END, save_csv=True):
    """
    Runs the full pipeline for ONE pair: data -> signals -> backtest -> stats.

    strategy: a strategy's name — the filename (without .py) of a file in
              the /strategies folder; they're discovered automatically.
    params:   that strategy's own knobs, e.g. {"window": 20}. Anything left
              out falls back to the strategy's declared default. Stop, target
              and hold time are NOT strategy params — they belong to the
              engine and are separate arguments here.

    sl_pips / tp_pips / spread_pips are in PIPS — they get converted to this
    pair's price units right here, so the engine never needs to know which
    instrument it's testing. Leave them as None to use the pair's own values
    from core/pairs.py, or the global defaults otherwise.

    save_csv: write the trade list to results/. True for command-line runs
              (that's the record of a run); the dashboard passes False, since
              re-running on every slider tweak would bury results/ in files.

    Returns (trades, stats). This function is deliberately the one entry
    point for a single backtest — the dashboard calls it too, so the
    dashboard and the command line can never drift apart.
    """
    pair = get_pair(pair_name)
    if sl_pips is None:
        sl_pips = pair.get("sl_pips", DEFAULT_SL_PIPS)
    if tp_pips is None:
        tp_pips = pair.get("tp_pips", DEFAULT_TP_PIPS)
    if spread_pips is None:
        spread_pips = pair.get("spread_pips", 0)

    data = get_data(pair["ticker"], start, end)
    data, resolved = apply_strategy(data, strategy, params)

    trades = run_backtest(
        data,
        stop_loss=pips_to_price(pair_name, sl_pips),
        take_profit=pips_to_price(pair_name, tp_pips),
        max_hold_days=max_hold_days,
        spread=pips_to_price(pair_name, spread_pips),
    )

    # Filename carries the pair, the strategy's own short name and the
    # parameters, so runs stop overwriting each other and you can always tell
    # which settings produced a file.
    if save_csv:
        slug = strategy_slug(strategy, resolved)
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        trades.to_csv(
            RESULTS_DIR / f"{pair_name}_{slug}_sl{sl_pips}_tp{tp_pips}_sp{spread_pips}.csv",
            index=False,
        )

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
