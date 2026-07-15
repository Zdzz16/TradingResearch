"""
Broker sync — placeholder.

This is where filled trades get pulled from a broker's API into the live
journal, so real trades land automatically instead of being typed in.

Nothing is implemented because no broker is chosen yet (see docs/notes.md).
OANDA is the front-runner — good REST API, free practice account, and we may
use their bid/ask data anyway — but it is not decided.

The shape is fixed even though the broker isn't: whatever we connect to, its
job is to produce rows for journal.live_journal, which already match the
backtest schema. So the rest of the platform doesn't need to know or care
which broker it is.

What any implementation of this has to solve:

  * Identity — the broker's ticket/order id goes in `run_id`, so a trade
    synced twice updates its row instead of duplicating it.
  * Stop distance — brokers report fills, not intent. `stop_distance` is what
    makes R-multiples possible, so it has to come from the order's stop level
    at entry, and if the broker won't give it, from what we recorded when
    placing the trade. A synced trade with no stop distance can't be compared
    to the backtest in R.
  * Partial fills and scaling — one "trade" in this journal is one position;
    a broker may fill it in pieces. Decide whether to aggregate to an average
    entry or store each fill.
  * Costs — the broker's profit figure already includes spread, commission and
    financing. The backtest models those separately. Store the broker's number
    as truth; that difference IS the measurement we're after.
  * Credentials — an API token. It belongs in an environment variable, never
    in this repo.
"""


class BrokerNotConfigured(RuntimeError):
    """Raised until a broker is actually wired up."""


def sync_fills(since=None):
    """
    Pull filled trades from the broker and upsert them into the live journal.

    since: only fetch trades after this timestamp. None = everything.

    Returns the number of trades added/updated once implemented.
    """
    raise BrokerNotConfigured(
        "No broker is connected yet. Choose one first (see docs/notes.md — "
        "OANDA is the likely candidate), then implement sync_fills()."
    )


def fetch_open_positions():
    """What the broker currently has open — for reconciling against the
    live journal's open trades and catching anything that drifted."""
    raise BrokerNotConfigured("No broker is connected yet.")
