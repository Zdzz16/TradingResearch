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
