"""
TradingResearch dashboard — the interactive front end lives here.

Planned shape (Streamlit): pick pairs, adjust stop/target in pips, and
see results side by side — in-sample vs out-of-sample — all powered by
the SAME run_strategy() pipeline the command line uses, so the dashboard
can never drift from the tested engine. Core logic stays in core/;
this folder only presents it.

Run (once built):  streamlit run dashboard/app.py
"""

# The dashboard will import the tested pipeline rather than re-implement it:
# from run_backtest import run_strategy
