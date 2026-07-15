"""
Journal — the record of trades, split in two.

  backtest_journal   runs produced by the backtesting engine
  live_journal       real trades (typed in now, broker-synced later)
  broker_sync        placeholder for the broker API connection
  storage            the shared SQLite setup both journals sit on

Both journals use the exact same schema (one column list, in storage.py, that
builds both tables), so they never mix but always compare — the same analysis
and the same UI work on either, and "did live match what the backtest
promised?" becomes answerable.

Typical use:

    from journal import backtest_journal, live_journal

    run_id = backtest_journal.save_run(trades, asset="EURUSD")
    backtest_journal.fetch_run(run_id)

    tid = live_journal.open_trade("EURUSD", "buy", 1.0850, stop_distance=0.0050)
    live_journal.close_trade(tid, exit_price=1.0910)
"""

from journal import backtest_journal, broker_sync, live_journal, storage

__all__ = ["backtest_journal", "live_journal", "broker_sync", "storage"]
