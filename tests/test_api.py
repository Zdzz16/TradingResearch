import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))
from app import app as flask_app  # noqa: E402


@pytest.fixture
def client():
    flask_app.config["TESTING"] = False   # keep our error handlers live
    with flask_app.test_client() as c:
        yield c


def post(client, path, payload):
    return client.post(path, data=json.dumps(payload),
                       content_type="application/json")


# ---------- the API must always speak JSON ----------

def test_malformed_input_is_a_400_with_a_message_not_a_500():
    """int(body['max_hold_days']) on garbage used to raise a bare ValueError
    that escaped as a 500 — the server blaming itself for a bad request."""
    with flask_app.test_client() as c:
        r = post(c, "/api/backtest", {"pairs": ["EURUSD"], "max_hold_days": "banana"})
    assert r.status_code == 400
    assert "max_hold_days" in r.get_json()["error"]
    assert "number" in r.get_json()["error"]


def test_unknown_endpoint_returns_json_not_an_html_page(client):
    r = client.get("/api/nope")
    assert r.status_code == 404
    assert r.is_json and "No such endpoint" in r.get_json()["error"]


def test_broken_json_body_is_reported_clearly(client):
    r = client.post("/api/backtest", data="{not json",
                    content_type="application/json")
    assert r.status_code == 400
    assert "valid JSON" in r.get_json()["error"]


def test_body_must_be_an_object(client):
    r = client.post("/api/backtest", data="[1,2,3]",
                    content_type="application/json")
    assert r.status_code == 400
    assert "JSON object" in r.get_json()["error"]


# ---------- validation says what is wrong ----------

def test_no_pairs_is_rejected(client):
    assert post(client, "/api/backtest", {}).status_code == 400
    r = post(client, "/api/backtest", {"pairs": []})
    assert "at least one pair" in r.get_json()["error"]


def test_unknown_pair_lists_the_real_ones(client):
    r = post(client, "/api/backtest", {"pairs": ["DOGEUSD"]})
    assert r.status_code == 400
    err = r.get_json()["error"]
    assert "DOGEUSD" in err and "EURUSD" in err


def test_out_of_range_numbers_are_rejected_with_the_limit(client):
    r = post(client, "/api/backtest", {"pairs": ["EURUSD"], "max_hold_days": 0})
    assert r.status_code == 400 and "at least 1" in r.get_json()["error"]

    r = post(client, "/api/backtest", {"pairs": ["EURUSD"], "max_hold_days": 9999})
    assert r.status_code == 400 and "at most 365" in r.get_json()["error"]


def test_unknown_strategy_is_a_400(client):
    r = post(client, "/api/backtest", {"pairs": ["EURUSD"], "strategy": "nope"})
    assert r.status_code == 400
    assert "Unknown strategy" in r.get_json()["error"]


def test_bad_strategy_param_is_a_400(client):
    r = post(client, "/api/backtest",
             {"pairs": ["EURUSD"], "params": {"window": 1}})
    assert r.status_code == 400
    assert "at least 2" in r.get_json()["error"]


# ---------- dates: the in-sample / out-of-sample unlock ----------

def test_bad_date_is_reported(client):
    r = post(client, "/api/backtest", {"pairs": ["EURUSD"], "start": "not-a-date"})
    assert r.status_code == 400 and "date like" in r.get_json()["error"]


def test_start_must_precede_end(client):
    r = post(client, "/api/backtest",
             {"pairs": ["EURUSD"], "start": "2024-01-01", "end": "2020-01-01"})
    assert r.status_code == 400 and "must be before" in r.get_json()["error"]


def test_a_narrower_window_yields_fewer_trades(client):
    """This is what makes an in-sample / out-of-sample split possible."""
    full = post(client, "/api/backtest", {"pairs": ["EURUSD"]}).get_json()
    half = post(client, "/api/backtest",
                {"pairs": ["EURUSD"], "start": "2015-01-01", "end": "2020-01-01"}).get_json()
    assert len(half["trades"]) < len(full["trades"])
    assert half["settings"]["end"] == "2020-01-01"
    assert all(t["entry_date"] < "2020-01-01" for t in half["trades"])


# ---------- the happy path still works ----------

def test_backtest_returns_series_stats_and_trades(client):
    r = post(client, "/api/backtest", {"pairs": ["EURUSD"], "params": {"window": 20}})
    assert r.status_code == 200
    d = r.get_json()
    assert len(d["trades"]) == 127          # the long-standing regression figure
    assert d["series"][0]["color"] == "#1f77b4"   # hex straight from the registry
    assert d["combined"]["breakeven_win_rate"] is not None


def test_reference_endpoints(client):
    pairs = client.get("/api/pairs").get_json()
    assert {p["name"] for p in pairs} == {"EURUSD", "GBPUSD", "USDJPY", "XAUUSD"}

    s = client.get("/api/strategies").get_json()
    assert s["strategies"][0]["name"] == "ma_crossover"
    assert s["defaults"]["start"] == "2015-01-01"


def test_favicon_is_served_instead_of_404ing_every_session(client):
    r = client.get("/favicon.ico")
    assert r.status_code == 200 and "svg" in r.mimetype


# ---------- account ----------

def test_account_sizes_a_real_backtest(client):
    r = post(client, "/api/account",
             {"pairs": ["EURUSD"], "initial_balance": 10_000,
              "risk_per_trade": 0.01, "leverage": 30})
    assert r.status_code == 200
    d = r.get_json()
    assert d["summary"]["initial_balance"] == 10_000
    assert d["summary"]["trades_taken"] + d["summary"]["trades_skipped"] == 127


def test_account_settings_are_validated(client):
    r = post(client, "/api/account", {"pairs": ["EURUSD"], "risk_per_trade": 5})
    assert r.status_code == 400 and "risk_per_trade" in r.get_json()["error"]

    r = post(client, "/api/account", {"pairs": ["EURUSD"], "leverage": 0})
    assert r.status_code == 400 and "leverage" in r.get_json()["error"]


def test_low_leverage_refuses_trades_through_the_api(client):
    r = post(client, "/api/account",
             {"pairs": ["EURUSD"], "leverage": 1, "risk_per_trade": 0.01})
    d = r.get_json()
    assert d["summary"]["trades_skipped"] > 0
    assert any(t["skip_reason"] and "margin" in t["skip_reason"] for t in d["trades"])


# ---------- saved runs (Compare) ----------

def test_runs_are_saved_per_strategy_AND_params(client):
    """Keyed by name alone, MA20 and MA50 would overwrite each other — and
    comparing a strategy against its own tuning is the cheap overfit check."""
    client.delete("/api/runs")
    post(client, "/api/backtest", {"pairs": ["EURUSD"], "params": {"window": 20}})
    post(client, "/api/backtest", {"pairs": ["EURUSD"], "params": {"window": 50}})
    runs = client.get("/api/runs").get_json()
    assert len(runs) == 2
    assert {r["params"]["window"] for r in runs} == {20, 50}


def test_rerunning_identical_settings_replaces_its_own_slot(client):
    client.delete("/api/runs")
    post(client, "/api/backtest", {"pairs": ["EURUSD"], "params": {"window": 20}})
    post(client, "/api/backtest", {"pairs": ["EURUSD"], "params": {"window": 20}})
    assert len(client.get("/api/runs").get_json()) == 1


def test_runs_can_be_cleared(client):
    post(client, "/api/backtest", {"pairs": ["EURUSD"], "params": {"window": 20}})
    assert client.delete("/api/runs").get_json()["cleared"] >= 1
    assert client.get("/api/runs").get_json() == []


# ---------- journal (Tracker) ----------

def test_journal_endpoints_answer(client, tmp_path, monkeypatch):
    from journal import live_journal, storage
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "api.db")

    tid = live_journal.open_trade("EURUSD", "buy", 1.0850, stop_distance=0.0050)
    live_journal.close_trade(tid, exit_price=1.0900)

    live = client.get("/api/journal/live").get_json()
    assert len(live) == 1
    assert round(live[0]["r_multiple"], 6) == 1.0   # R comes back for free
    assert client.get("/api/journal/live?open=1").get_json() == []
    assert client.get("/api/journal/runs").status_code == 200


# ---------- the cache must serve any window it already covers ----------

def test_a_sub_range_is_served_from_the_wide_cache_without_network(monkeypatch):
    """Caching by exact ticker+start+end meant every new window was a fresh
    download — so an in-sample/out-of-sample split would hit the network
    twice and leave two more cache files, despite the answer already sitting
    in the 2015-2024 file. Any download here is a failure."""
    import yfinance
    from core.data_loader import CACHE_DIR, get_data

    def boom(*a, **k):
        raise AssertionError("went to the network for data we already hold")
    monkeypatch.setattr(yfinance, "download", boom)

    before = set(CACHE_DIR.glob("*.csv"))
    ins = get_data("EURUSD=X", "2015-01-01", "2020-01-01")
    oos = get_data("EURUSD=X", "2021-01-01", "2024-12-31")

    assert len(ins) and len(oos)
    assert ins.index[-1] < oos.index[0]          # the split doesn't overlap
    assert str(ins.index[-1].date()) <= "2020-01-01"
    assert str(oos.index[0].date()) >= "2021-01-01"
    assert set(CACHE_DIR.glob("*.csv")) == before  # and nothing new was written


def test_an_uncovered_window_is_not_faked_from_a_narrower_cache(monkeypatch):
    """Only a cache that CONTAINS the window may answer it. Asking for
    2010 must not be quietly served the 2015-2024 file."""
    import yfinance
    from core import data_loader

    calls = []
    monkeypatch.setattr(yfinance, "download",
                        lambda *a, **k: calls.append(k) or __import__("pandas").DataFrame())
    with pytest.raises(ValueError, match="No data returned"):
        data_loader.get_data("EURUSD=X", "2010-01-01", "2012-01-01")
    assert calls, "should have tried to download a window we don't hold"
