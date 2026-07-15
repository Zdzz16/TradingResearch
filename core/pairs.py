"""
Single source of truth for every instrument this platform can backtest.

Why pips instead of raw price units? Because raw units mean something
different on every instrument: a 0.01 move is 100 pips on EURUSD, but
only 1 pip on USDJPY (which trades around 150.00), and a single cent on
gold (which trades in the thousands). Talking in pips at the edges — and
converting to price units per pair right before calling the engine —
lets one setting like "100 pip stop" mean roughly the same *kind* of
risk everywhere, while the engine itself stays simple and unit-agnostic.

Each pair also carries a fixed chart color, so a pair always looks the
same in every chart (and later, the dashboard reads the same field).

A note on gold (XAUUSD): Yahoo has no spot gold ticker, so we use GC=F
(COMEX gold futures) as a close proxy. Two caveats: futures sit a few
dollars off spot, and the continuous series has small price jumps when
the front-month contract rolls each month. Good enough for research on
daily bars; real spot data arrives later via a paid provider through
this same registry (just swap the ticker). Gold also overrides the
default stop/target: fixed distances sized for a ~1.10 currency make no
sense on a ~$2,000 instrument, so it uses 200/400 pips = $20/$40.
"""

# spread_pips: a typical retail round-trip spread for the pair — the cost
# of every trade, deducted by the engine. These are conservative ballpark
# figures; tighten or widen them to match your actual broker.
#
# base / quote: which currency each side of the price is in. EURUSD means
# "how many USD for one EUR" — base EUR, quote USD. This is what the account
# simulator needs to turn a price move into money:
#   * profit lands in the QUOTE currency (a EURUSD move pays USD; a USDJPY
#     move pays JPY and has to be converted).
#   * what you're borrowing to hold is measured in the BASE currency, so the
#     position's value in USD depends on whether the base already IS USD.
# XAU is gold: "base" is an ounce, priced in USD.
PAIRS = {
    "EURUSD": {"ticker": "EURUSD=X", "pip_size": 0.0001, "color": "tab:blue",
               "spread_pips": 1.0, "base": "EUR", "quote": "USD"},
    "GBPUSD": {"ticker": "GBPUSD=X", "pip_size": 0.0001, "color": "tab:green",
               "spread_pips": 1.5, "base": "GBP", "quote": "USD"},
    "USDJPY": {"ticker": "USDJPY=X", "pip_size": 0.01,   "color": "tab:red",
               "spread_pips": 1.0, "base": "USD", "quote": "JPY"},
    "XAUUSD": {"ticker": "GC=F",     "pip_size": 0.1,    "color": "goldenrod",
               "spread_pips": 3.5, "sl_pips": 200, "tp_pips": 400,
               "base": "XAU", "quote": "USD"},
}

# Used for any pair that doesn't override them. 100/200 pips on EURUSD
# equals the 0.01/0.02 price units all results so far were produced with.
DEFAULT_SL_PIPS = 100
DEFAULT_TP_PIPS = 200


def get_pair(pair_name):
    """Returns one pair's config, with a helpful error if the name is unknown."""
    if pair_name not in PAIRS:
        raise ValueError(
            f"Unknown pair '{pair_name}'. Available pairs: {', '.join(PAIRS)}"
        )
    return PAIRS[pair_name]


def pips_to_price(pair_name, pips):
    """Converts a distance in pips to this pair's price units."""
    return pips * get_pair(pair_name)["pip_size"]
