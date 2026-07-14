import yfinance as yf
import pandas as pd
import os

CACHE_DIR = "data_cache"

def get_data(ticker, start, end):
    """
    Downloads historical price data and cleans it up — but only if we don't
    already have a local copy saved. Local copies live in data_cache/, named
    after the ticker and date range, so different requests don't collide.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = f"{CACHE_DIR}/{ticker.replace('=', '')}_{start}_{end}.csv"

    if os.path.exists(cache_file):
        # We've downloaded this exact ticker+range before — load it locally,
        # much faster than hitting Yahoo again. index_col=0 tells pandas the
        # first column (Date) should be the row label, not a normal column.
        data = pd.read_csv(cache_file, index_col=0, parse_dates=True)
        return data

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

    data.to_csv(cache_file)
    return data