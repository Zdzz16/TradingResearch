import yfinance as yf
import pandas as pd
from pathlib import Path

# Anchored to the project root, NOT the working directory. A relative path
# here meant the cache landed wherever you happened to launch from — so a
# run from another folder silently re-downloaded ten years of data into a
# second cache. It's also what forced the dashboard to os.chdir on import.
CACHE_DIR = Path(__file__).resolve().parent.parent / "data_cache"

REQUIRED_PRICE_COLUMNS = ["Open", "High", "Low", "Close"]


def _read_cache(path):
    """Loads a cache file, complaining usefully if it's corrupt."""
    # index_col=0 tells pandas the first column (Date) is the row label,
    # not a normal column.
    data = pd.read_csv(path, index_col=0, parse_dates=True)
    missing = [c for c in REQUIRED_PRICE_COLUMNS if c not in data.columns]
    if missing:
        # A truncated or corrupt cache file used to blow up with a bare
        # KeyError. Say what's wrong and how to fix it.
        raise ValueError(
            f"Cache file {path.name} is missing column(s): "
            f"{', '.join(missing)}. Delete it and it will re-download."
        )
    # Drop rows with missing prices — the engine (rightly) refuses them.
    return data.dropna(subset=REQUIRED_PRICE_COLUMNS)


def _covering_cache(ticker, start, end):
    """Finds a cached file whose range CONTAINS the one being asked for.

    Caching by exact ticker+start+end meant every new window was a fresh
    download — so an in-sample/out-of-sample split (2015-2020 then 2021-2024)
    would hit the network twice and leave two more files, despite the answer
    already sitting in the 2015-2024 file we already have. A wider cache
    answers any window inside it, offline and instantly.
    """
    prefix = f"{ticker.replace('=', '')}_"
    for path in sorted(CACHE_DIR.glob(f"{prefix}*.csv")):
        span = path.stem[len(prefix):]
        parts = span.split("_")
        if len(parts) != 2:
            continue
        cached_start, cached_end = parts
        if cached_start <= start and cached_end >= end:
            return path
    return None


def get_data(ticker, start, end):
    """
    Returns clean OHLCV data for a ticker between two dates.

    Uses a local copy when we already hold one covering the window — that
    includes any narrower slice of a range downloaded earlier — and only
    goes to the network when we genuinely don't have the data.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    covering = _covering_cache(ticker, start, end)
    if covering is not None:
        # loc on a DatetimeIndex slices inclusively at both ends
        return _read_cache(covering).loc[start:end]

    cache_file = CACHE_DIR / f"{ticker.replace('=', '')}_{start}_{end}.csv"

    # No local copy yet — download fresh, then save it for next time.
    data = yf.download(ticker, start=start, end=end, auto_adjust=True)

    if data.empty:
        # Fail loudly with a useful message — an empty result would otherwise
        # sail through the whole pipeline and end in a confusing
        # "No trades to summarize" with no hint that the data never arrived.
        raise ValueError(
            f"No data returned for '{ticker}' ({start} to {end}). "
            "Check the ticker symbol (see core/pairs.py) and your connection."
        )

    # yfinance sometimes returns two-level column names (price, ticker)
    # depending on its version — only flatten when that's actually the case.
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.droplevel(1)

    # Drop rows with missing prices BEFORE caching, so the cache is clean
    # and the engine (which rightly refuses NaN prices) never sees them.
    data = data.dropna(subset=REQUIRED_PRICE_COLUMNS)

    data.to_csv(cache_file)
    return data