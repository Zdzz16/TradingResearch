from core.data_loader import get_data
from core.strategies import ma_crossover
from core.engine import run_backtest
from core.analysis import summarize
from core.plotting import plot_equity_curve

data = get_data("EURUSD=X", "2015-01-01", "2024-12-31")
data = ma_crossover(data, window=20)

trades = run_backtest(
    data,
    stop_loss=0.01,
    take_profit=0.02,
    max_hold_days=10
)

trades.to_csv("results/ma20_stop_target.csv", index=False)

summarize(trades)
plot_equity_curve(trades, title="Equity Curve — MA20 Crossover (Stop/Target)")