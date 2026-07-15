import yfinance as yf
import pandas as pd
from pathlib import Path

# Anchored to the project root, NOT the working directory. A relative path
# here meant the cache landed wherever you happened to launch from — so a
# run from another folder silently re-downloaded ten years of data into a
# second cache. It's also what forced the dashboard to os.chdir on import.
CACHE_DIR = Path(__file__).resolve().parent.parent / "data_cache"

REQUIRED_PRICE_COLUMNS = ["Open", "High", "Low", "Close"]


def get_data(ticker, start, end):
    """
    Downloads historical price data and cleans it up — but only if we don't
    already have a local copy saved. Local copies live in data_cache/, named
    after the ticker and date range, so different requests don't collide.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{ticker.replace('=', '')}_{start}_{end}.csv"

    if cache_file.exists():
        # We've downloaded this exact ticker+range before — load it locally,
        # much faster than hitting Yahoo again. index_col=0 tells pandas the
        # first column (Date) should be the row label, not a normal column.
        data = pd.read_csv(cache_file, index_col=0, parse_dates=True)
        missing = [c for c in REQUIRED_PRICE_COLUMNS if c not in data.columns]
        if missing:
            # A truncated or corrupt cache file used to blow up with a bare
            # KeyError. Say what's wrong and how to fix it.
            raise ValueError(
                f"Cache file {cache_file.name} is missing column(s): "
                f"{', '.join(missing)}. Delete it and it will re-download."
            )
        # Drop rows with missing prices — the engine (rightly) refuses them.
        return data.dropna(subset=REQUIRED_PRICE_COLUMNS)

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