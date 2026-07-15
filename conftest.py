# Deliberately (almost) empty — but load-bearing: pytest sees this file at
# the project root and puts the root on sys.path, which is what lets tests
# do `from core.engine import run_backtest`. Do not delete.
