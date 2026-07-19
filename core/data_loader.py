import shutil
import subprocess
import tempfile
from pathlib import Path

import pandas as pd
import yfinance as yf

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


def _cache_prefix(symbol, source):
    """Cache filenames are namespaced by source so the two never mix.

    Yahoo keeps its original naming so the committed cache files (and the
    long-standing regression baselines built on them) stay valid.
    """
    if source == "yahoo":
        return f"{symbol.replace('=', '')}_"
    return f"{source}_{symbol}_"


def _to_trading_days(data):
    """Turns Dukascopy's CALENDAR-day bars into trading-day bars.

    Dukascopy emits a bar for all seven days. That is not what it looks like:
      * Saturday bars are flat placeholders (O==H==L==C) — the market is shut.
      * Sunday bars ARE real, but only cover the couple of hours after the
        weekly open at 22:00 UTC.

    Left alone this quietly corrupts everything downstream: a 20-bar moving
    average would span 20 CALENDAR days (~14 trading days), and "hold for 10
    days" would count weekends as holding time. Yahoo gave weekday bars, so
    the two sources wouldn't even be comparable.

    So: drop Saturdays, and fold Sunday's session into Monday's bar rather
    than discarding it — Sunday's open IS the true weekly open, and that is
    where the weekend gap lives. Our engine is gap-aware, so keeping the real
    gap matters more than the tidiness of dropping it.
    """
    data = data[data.index.dayofweek != 5]              # no trading Saturdays

    dates = data.index.to_series()
    is_sunday = data.index.dayofweek == 6
    dates[is_sunday] = dates[is_sunday] + pd.Timedelta(days=1)
    data = data.set_index(pd.DatetimeIndex(dates, name="Date"))

    # Rows keep their original order within a date, so 'first' is Sunday's
    # (weekly) open and 'last' is Monday's close.
    return data.groupby(level=0).agg({"Open": "first", "High": "max",
                                      "Low": "min", "Close": "last"})


def _download_dukascopy(symbol, start, end):
    """Fetches daily bars from Dukascopy via the dukascopy-node CLI.

    Dukascopy publishes real traded prices from its ECN pool (and real spot
    gold, which Yahoo has no ticker for) — free, no account. We shell out to
    the Node tool rather than reimplement their binary tick format.

    Prices are BID. Our engine models the spread as an explicit cost, so a
    single-sided series is the right input — using mid would double-count
    half the spread.
    """
    if shutil.which("npx") is None:
        raise ValueError(
            "Dukascopy needs Node.js (npx) on PATH. Install Node, or pass "
            "source='yahoo'."
        )

    work_dir = Path(tempfile.mkdtemp(prefix="dukascopy_"))
    try:
        result = subprocess.run(
            ["npx", "--yes", "dukascopy-node@latest",
             "-i", symbol, "-from", start, "-to", end,
             "-t", "d1", "-f", "csv"],
            cwd=work_dir, capture_output=True, text=True, timeout=600,
        )
        files = sorted((work_dir / "download").glob("*.csv"))
        if result.returncode != 0 or not files:
            raise ValueError(
                f"Dukascopy download failed for '{symbol}' ({start} to {end}). "
                f"{(result.stderr or result.stdout or '').strip()[-300:]}"
            )

        raw = pd.read_csv(files[0])
        if raw.empty:
            raise ValueError(
                f"Dukascopy returned no rows for '{symbol}' ({start} to {end})."
            )

        # epoch milliseconds -> a DatetimeIndex named Date, and their
        # lowercase columns -> the capitalised names the engine expects.
        raw["Date"] = pd.to_datetime(raw["timestamp"], unit="ms")
        data = (raw.rename(columns={"open": "Open", "high": "High",
                                    "low": "Low", "close": "Close"})
                   .set_index("Date")[REQUIRED_PRICE_COLUMNS])
        return _to_trading_days(data.sort_index())
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def _download_yahoo(symbol, start, end):
    data = yf.download(symbol, start=start, end=end, auto_adjust=True)

    if data.empty:
        # Fail loudly with a useful message — an empty result would otherwise
        # sail through the whole pipeline and end in a confusing
        # "No trades to summarize" with no hint that the data never arrived.
        raise ValueError(
            f"No data returned for '{symbol}' ({start} to {end}). "
            "Check the ticker symbol (see core/pairs.py) and your connection."
        )

    # yfinance sometimes returns two-level column names (price, ticker)
    # depending on its version — only flatten when that's actually the case.
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.droplevel(1)
    return data


def _covering_cache(prefix, start, end):
    """Finds a cached file whose range CONTAINS the one being asked for.

    Caching by exact ticker+start+end meant every new window was a fresh
    download — so an in-sample/out-of-sample split (2015-2020 then 2021-2024)
    would hit the network twice and leave two more files, despite the answer
    already sitting in the 2015-2024 file we already have. A wider cache
    answers any window inside it, offline and instantly.
    """
    for path in sorted(CACHE_DIR.glob(f"{prefix}*.csv")):
        span = path.stem[len(prefix):]
        parts = span.split("_")
        if len(parts) != 2:
            continue
        cached_start, cached_end = parts
        if cached_start <= start and cached_end >= end:
            return path
    return None


def get_data(symbol, start, end, source="yahoo"):
    """
    Returns clean OHLC data for a symbol between two dates.

    source: "dukascopy" (real traded prices, real spot gold) or "yahoo".
            The symbol must be the one THAT source uses — see
            core.pairs.symbol_for(), which maps a pair to the right one.

    Uses a local copy when we already hold one covering the window (including
    any narrower slice of a wider download), and only goes to the network when
    we genuinely don't have the data. Caches are namespaced per source so the
    two never mix.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    prefix = _cache_prefix(symbol, source)

    covering = _covering_cache(prefix, start, end)
    if covering is not None:
        # loc on a DatetimeIndex slices inclusively at both ends
        return _read_cache(covering).loc[start:end]

    if source == "dukascopy":
        data = _download_dukascopy(symbol, start, end)
    elif source == "yahoo":
        data = _download_yahoo(symbol, start, end)
    else:
        raise ValueError(f"Unknown data source '{source}'.")

    # Drop rows with missing prices BEFORE caching, so the cache is clean
    # and the engine (which rightly refuses NaN prices) never sees them.
    data = data.dropna(subset=REQUIRED_PRICE_COLUMNS)

    data.to_csv(CACHE_DIR / f"{prefix}{start}_{end}.csv")
    return data
