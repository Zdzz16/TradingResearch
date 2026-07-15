import pandas as pd
import pytest

from journal import backtest_journal, broker_sync, live_journal, storage


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Every test gets its own throwaway database — tests must never touch
    the real journal."""
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "test.db")


# ---------- the shared schema ----------

def test_both_tables_have_the_exact_same_schema():
    """The point of the split: separate records, identical shape — so one UI
    component displays either, and the two compare like for like."""
    conn = storage.connect()
    try:
        shape = {}
        for table in storage.TABLES:
            cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
            shape[table] = [(c["name"], c["type"]) for c in cols]
    finally:
        conn.close()

    assert shape[storage.BACKTEST_TABLE] == shape[storage.LIVE_TABLE]
    names = [n for n, _ in shape[storage.BACKTEST_TABLE]]
    # everything the issue asks the schema to carry
    for required in ("asset", "entry_price", "exit_price", "direction",
                     "volume", "profit", "entry_timestamp"):
        assert required in names


def test_the_two_journals_never_mix():
    live_journal.open_trade("EURUSD", "buy", 1.0850)
    backtest_journal.save_run(
        [{"entry_date": "2024-01-01", "exit_date": "2024-01-02", "direction": "long",
          "entry_price": 1.1, "exit_price": 1.2, "profit": 0.1, "r_multiple": 1.0,
          "exit_reason": "take_profit"}],
        asset="GBPUSD", run_id="r1",
    )
    live = live_journal.fetch_trades()
    bt = backtest_journal.fetch_all()
    assert len(live) == 1 and live[0]["asset"] == "EURUSD"
    assert len(bt) == 1 and bt[0]["asset"] == "GBPUSD"


def test_direction_must_be_buy_or_sell():
    with pytest.raises(ValueError, match="buy.*sell"):
        live_journal.open_trade("EURUSD", "long", 1.0850)


def test_unknown_field_is_rejected():
    with pytest.raises(ValueError, match="Unknown field"):
        storage.insert(storage.LIVE_TABLE, [{
            "asset": "EURUSD", "direction": "buy", "entry_price": 1.0,
            "entry_timestamp": "2024-01-01", "nonsense": 1,
        }])


def test_unknown_table_is_rejected():
    with pytest.raises(ValueError, match="Unknown table"):
        storage.fetch("some_other_table")


# ---------- the bug that made the old journal dangerous ----------

def test_closing_a_nonexistent_trade_raises_instead_of_inventing_one():
    """The old journal used pandas .loc, which SILENTLY CREATED a row when
    given an index that didn't exist — in the real-money record. A bad id
    must be an error and must never add a trade."""
    live_journal.open_trade("EURUSD", "buy", 1.0850)

    with pytest.raises(KeyError):
        live_journal.close_trade(999, exit_price=1.09)

    assert len(live_journal.fetch_trades()) == 1  # nothing was invented


def test_a_trade_cannot_be_closed_twice():
    tid = live_journal.open_trade("EURUSD", "buy", 1.0850)
    live_journal.close_trade(tid, exit_price=1.0900)
    with pytest.raises(ValueError, match="already closed"):
        live_journal.close_trade(tid, exit_price=1.0950)


# ---------- live journal ----------

def test_open_then_close_computes_profit_for_a_buy():
    tid = live_journal.open_trade("EURUSD", "buy", 1.0850, stop_distance=0.0050)
    trade = live_journal.close_trade(tid, exit_price=1.0900)
    assert round(trade["profit"], 6) == 0.0050
    assert trade["exit_reason"] == "manual"
    assert trade["exit_timestamp"] is not None


def test_profit_for_a_sell_is_the_other_way_round():
    tid = live_journal.open_trade("EURUSD", "sell", 1.0850)
    trade = live_journal.close_trade(tid, exit_price=1.0800)
    assert round(trade["profit"], 6) == 0.0050


def test_volume_scales_profit():
    tid = live_journal.open_trade("EURUSD", "buy", 1.0850, volume=2)
    trade = live_journal.close_trade(tid, exit_price=1.0900)
    assert round(trade["profit"], 6) == 0.0100


def test_broker_profit_wins_over_our_arithmetic():
    """The broker's number includes fees and slippage; that difference is
    exactly what we want to measure, so it must not be overwritten."""
    tid = live_journal.open_trade("EURUSD", "buy", 1.0850)
    trade = live_journal.close_trade(tid, exit_price=1.0900, profit=0.0043)
    assert trade["profit"] == 0.0043


def test_open_only_filter():
    live_journal.open_trade("EURUSD", "buy", 1.0850)
    closed = live_journal.open_trade("GBPUSD", "buy", 1.2600)
    live_journal.close_trade(closed, exit_price=1.2650)
    assert len(live_journal.fetch_trades()) == 2
    assert len(live_journal.fetch_trades(open_only=True)) == 1


def test_r_multiple_needs_the_stop_logged_at_entry():
    with_stop = live_journal.open_trade("EURUSD", "buy", 1.0850, stop_distance=0.0050)
    trade = live_journal.close_trade(with_stop, exit_price=1.0900)
    assert round(live_journal.r_multiple(trade), 6) == 1.0  # made exactly what it risked

    without = live_journal.open_trade("EURUSD", "buy", 1.0850)
    trade2 = live_journal.close_trade(without, exit_price=1.0900)
    assert live_journal.r_multiple(trade2) is None  # nothing to divide by

    still_open = live_journal.get_trade(live_journal.open_trade("EURUSD", "buy", 1.0, stop_distance=0.01))
    assert live_journal.r_multiple(still_open) is None


def test_stop_distance_must_be_positive():
    with pytest.raises(ValueError, match="positive"):
        live_journal.open_trade("EURUSD", "buy", 1.0850, stop_distance=-0.005)


# ---------- backtest journal ----------

def engine_trades():
    """Shaped like what core/engine.py actually returns."""
    return pd.DataFrame([
        {"entry_date": pd.Timestamp("2024-01-02"), "exit_date": pd.Timestamp("2024-01-04"),
         "direction": "long", "entry_price": 1.1000, "exit_price": 1.1200,
         "profit": 0.0200, "r_multiple": 2.0, "exit_reason": "take_profit"},
        {"entry_date": pd.Timestamp("2024-01-06"), "exit_date": pd.Timestamp("2024-01-07"),
         "direction": "short", "entry_price": 1.1200, "exit_price": 1.1300,
         "profit": -0.0100, "r_multiple": -1.0, "exit_reason": "stop_loss"},
    ])


def test_save_run_translates_the_engine_into_the_shared_schema():
    run_id = backtest_journal.save_run(engine_trades(), asset="EURUSD", run_id="run-1")
    rows = backtest_journal.fetch_run(run_id)

    assert len(rows) == 2
    assert [r["direction"] for r in rows] == ["buy", "sell"]   # long/short -> buy/sell
    assert rows[0]["asset"] == "EURUSD"
    assert rows[0]["entry_timestamp"].startswith("2024-01-02")
    # stop distance recovered from profit / r_multiple, so R stays computable
    assert round(rows[0]["stop_distance"], 6) == 0.01
    # the engine models price, not size — NULL is the honest answer
    assert rows[0]["volume"] is None


def test_rerunning_the_same_run_replaces_it_instead_of_duplicating():
    backtest_journal.save_run(engine_trades(), asset="EURUSD", run_id="run-1")
    backtest_journal.save_run(engine_trades(), asset="EURUSD", run_id="run-1")
    assert len(backtest_journal.fetch_run("run-1")) == 2


def test_runs_are_kept_apart_and_summarised():
    backtest_journal.save_run(engine_trades(), asset="EURUSD", run_id="run-1")
    backtest_journal.save_run(engine_trades(), asset="GBPUSD", run_id="run-2")

    runs = {r["run_id"]: r for r in backtest_journal.list_runs()}
    assert set(runs) == {"run-1", "run-2"}
    assert runs["run-1"]["trades"] == 2
    assert round(runs["run-1"]["profit"], 5) == 0.01
    assert runs["run-2"]["asset"] == "GBPUSD"


def test_delete_run_leaves_the_others_alone():
    backtest_journal.save_run(engine_trades(), asset="EURUSD", run_id="run-1")
    backtest_journal.save_run(engine_trades(), asset="GBPUSD", run_id="run-2")
    assert backtest_journal.delete_run("run-1") == 2
    assert backtest_journal.fetch_run("run-1") == []
    assert len(backtest_journal.fetch_run("run-2")) == 2


def test_run_id_is_generated_when_not_given():
    run_id = backtest_journal.save_run(engine_trades(), asset="EURUSD")
    assert run_id.startswith("EURUSD-")
    assert len(backtest_journal.fetch_run(run_id)) == 2


def test_a_half_written_run_is_not_written_at_all():
    """All-or-nothing: a bad trade in the middle must not leave a partial run
    behind, because a partial backtest is worse than no backtest."""
    good = engine_trades().to_dict("records")
    rows = [backtest_journal._to_row(t, "EURUSD", "run-x") for t in good]
    rows[1]["nonsense_column"] = 1  # will be rejected mid-transaction

    with pytest.raises(ValueError):
        storage.insert(storage.BACKTEST_TABLE, rows)
    assert backtest_journal.fetch_run("run-x") == []


# ---------- broker placeholder ----------

def test_broker_sync_says_it_is_not_configured_yet():
    with pytest.raises(broker_sync.BrokerNotConfigured):
        broker_sync.sync_fills()
    with pytest.raises(broker_sync.BrokerNotConfigured):
        broker_sync.fetch_open_positions()
