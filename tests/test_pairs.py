import pytest

from core.pairs import PAIRS, get_pair, pips_to_price

def test_pips_convert_using_each_pairs_own_pip_size():
    """
    The same "100 pips" is a different price distance on every instrument —
    which is the whole reason the registry exists. (pytest.approx because
    multiplying floats can be off by a hair, e.g. 100 * 0.0001 may not be
    EXACTLY 0.01 in binary floating point.)
    """
    assert pips_to_price("EURUSD", 100) == pytest.approx(0.01)
    assert pips_to_price("USDJPY", 100) == pytest.approx(1.00)
    assert pips_to_price("XAUUSD", 100) == pytest.approx(10.0)

def test_every_pair_has_the_fields_the_platform_relies_on():
    """The loader needs 'ticker', the conversion needs 'pip_size',
    and the comparison chart needs 'color' — for every pair, always."""
    for name, pair in PAIRS.items():
        assert "ticker" in pair, f"{name} is missing its Yahoo ticker"
        assert "pip_size" in pair, f"{name} is missing its pip size"
        assert "color" in pair, f"{name} is missing its chart color"

def test_unknown_pair_gives_a_helpful_error():
    with pytest.raises(ValueError, match="Unknown pair"):
        get_pair("DOGEUSD")


# ---------- data sources ----------

def test_every_pair_has_a_symbol_at_both_sources():
    from core.pairs import symbol_for
    for name in PAIRS:
        assert symbol_for(name, "yahoo")
        assert symbol_for(name, "dukascopy")


def test_gold_is_real_spot_on_dukascopy_but_a_futures_proxy_on_yahoo():
    """The main reason to switch: Yahoo has no spot gold ticker."""
    from core.pairs import symbol_for
    assert symbol_for("XAUUSD", "yahoo") == "GC=F"        # futures proxy
    assert symbol_for("XAUUSD", "dukascopy") == "xauusd"  # real spot


def test_unknown_source_is_rejected():
    from core.pairs import symbol_for
    with pytest.raises(ValueError, match="Unknown data source"):
        symbol_for("EURUSD", "bloomberg")


def test_dukascopy_calendar_days_are_folded_into_trading_days():
    """Dukascopy emits all 7 days: flat Saturday placeholders, and Sunday
    bars covering only the hours after the weekly open. Left raw, a 20-bar
    MA would span 20 CALENDAR days. Saturdays go; Sunday folds into Monday
    so the true weekly-open gap survives."""
    import pandas as pd
    from core.data_loader import _to_trading_days

    idx = pd.to_datetime(["2015-01-02",   # Fri
                          "2015-01-03",   # Sat - flat placeholder
                          "2015-01-04",   # Sun - the weekly open
                          "2015-01-05"])  # Mon
    raw = pd.DataFrame({"Open":  [1.20, 1.2002, 1.1950, 1.1930],
                        "High":  [1.21, 1.2002, 1.1960, 1.1975],
                        "Low":   [1.19, 1.2002, 1.1868, 1.1900],
                        "Close": [1.20, 1.2002, 1.1947, 1.1960]}, index=idx)
    out = _to_trading_days(raw)

    assert list(out.index.dayofweek) == [4, 0]          # Friday, Monday only
    monday = out.loc["2015-01-05"]
    assert monday["Open"] == 1.1950                     # Sunday's weekly open
    assert monday["Close"] == 1.1960                    # Monday's close
    assert monday["Low"] == 1.1868                      # deepest of both
    assert monday["High"] == 1.1975
