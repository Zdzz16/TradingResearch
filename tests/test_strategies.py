import pandas as pd
import pytest

from core import strategies as S


def test_ma_crossover_is_discovered_from_the_folder():
    """Nothing registers ma_crossover anywhere — it's found because the file
    exists in /strategies. That's the whole point of the folder."""
    found = S.load_strategies()
    assert "ma_crossover" in found
    assert found["ma_crossover"]["label"] == "MA crossover"
    assert callable(found["ma_crossover"]["fn"])


def test_declared_params_are_what_the_dashboard_renders():
    p = S.load_strategies()["ma_crossover"]["params"][0]
    assert p["name"] == "window" and p["default"] == 20
    assert p["min"] == 2 and p["max"] == 200


def test_params_resolve_cast_and_validate():
    assert S.resolve_params("ma_crossover") == {"window": 20}
    # JSON gives us strings/floats; the declared type decides
    assert S.resolve_params("ma_crossover", {"window": "50"}) == {"window": 50}
    with pytest.raises(ValueError, match="at least 2"):
        S.resolve_params("ma_crossover", {"window": 1})
    with pytest.raises(ValueError, match="at most 200"):
        S.resolve_params("ma_crossover", {"window": 500})


def test_unknown_strategy_says_what_is_available():
    with pytest.raises(ValueError, match="Unknown strategy"):
        S.get_strategy("does_not_exist")


def test_slug_keeps_result_filenames_stable():
    assert S.strategy_slug("ma_crossover", {"window": 20}) == "ma20"


def test_apply_strategy_marks_entries():
    """A rising series crosses its own 2-day average — at least one signal,
    and the engine's required column is present and boolean."""
    data = pd.DataFrame({
        "Open": [1, 1, 1, 1, 1.0],
        "High": [1, 1, 1, 1, 1.0],
        "Low": [1, 1, 1, 1, 1.0],
        "Close": [1.0, 0.9, 1.1, 1.2, 1.3],
    }, index=pd.date_range("2024-01-01", periods=5, freq="D"))

    out, resolved = S.apply_strategy(data, "ma_crossover", {"window": 2})
    assert resolved == {"window": 2}
    assert out["NewSignal"].dtype == bool
    assert out["NewSignal"].any()


def test_a_broken_file_is_reported_and_does_not_hide_the_good_ones(tmp_path, monkeypatch):
    """One typo in one strategy must not blank the whole picker — the bad
    file is skipped and named, the working ones still load."""
    folder = tmp_path / "strategies"
    folder.mkdir()
    (folder / "good.py").write_text(
        "LABEL = 'Good'\n"
        "def generate_signals(data):\n"
        "    data = data.copy()\n"
        "    data['NewSignal'] = False\n"
        "    return data\n"
    )
    (folder / "broken.py").write_text("this is not valid python (\n")
    (folder / "no_function.py").write_text("LABEL = 'Nope'\n")
    (folder / "_helper.py").write_text("raise RuntimeError('should never be imported')\n")

    monkeypatch.setattr(S, "STRATEGIES_DIR", folder)
    found = S.load_strategies()

    assert "good" in found                    # the working one survived
    assert "broken" not in found
    assert "_helper" not in found             # underscore files aren't strategies
    assert "broken" in S.load_errors
    assert "generate_signals" in S.load_errors["no_function"]


def test_a_new_file_appears_without_a_restart(tmp_path, monkeypatch):
    """The folder is re-scanned on every call, which is what lets you drop a
    strategy in and just refresh the page."""
    folder = tmp_path / "strategies"
    folder.mkdir()
    monkeypatch.setattr(S, "STRATEGIES_DIR", folder)
    assert S.load_strategies() == {}

    (folder / "later.py").write_text(
        "def generate_signals(data):\n"
        "    return data\n"
    )
    assert "later" in S.load_strategies()
