"""
Shared storage for both journals.

One schema, two tables. `backtest_trades` and `live_trades` are created from
the SAME column list below, so they cannot drift apart — which is the whole
point: a backtest trade and a live trade are the same shape, so one UI
component can display either, and the two can be compared like for like.
They live in separate tables so the records never mix.

SQLite, from the standard library: real tables, real transactions, no new
dependency, and a single file you can copy or delete.
"""

import sqlite3
from pathlib import Path

# The database is user data, not code — it sits at the project root and is
# gitignored. Delete the file and it rebuilds itself empty.
DB_PATH = Path(__file__).resolve().parent.parent / "journal.db"

BACKTEST_TABLE = "backtest_trades"
LIVE_TABLE = "live_trades"
TABLES = (BACKTEST_TABLE, LIVE_TABLE)

# THE schema. Both tables are built from this list, so "the exact same
# schema" is enforced by construction rather than by remembering to edit
# two places.
#
#   run_id         backtest: which run this trade belongs to.
#                  live: the broker's ticket/order id once we sync one.
#   direction      'buy' or 'sell' (the engine's long/short maps onto these).
#   volume         lot size. NULL for backtest trades — the engine models
#                  price, not position size; sizing is a separate layer.
#   stop_distance  how far the stop sat from entry, in price units. Logged at
#                  ENTRY because it can't be recovered afterwards, and without
#                  it there's no R-multiple: the broker will never tell you
#                  what your stop was meant to be.
COLUMNS = [
    ("id",              "INTEGER PRIMARY KEY AUTOINCREMENT"),
    ("run_id",          "TEXT"),
    ("asset",           "TEXT NOT NULL"),
    ("direction",       "TEXT NOT NULL CHECK (direction IN ('buy', 'sell'))"),
    ("entry_timestamp", "TEXT NOT NULL"),
    ("exit_timestamp",  "TEXT"),
    ("entry_price",     "REAL NOT NULL"),
    ("exit_price",      "REAL"),
    ("volume",          "REAL"),
    ("profit",          "REAL"),
    ("stop_distance",   "REAL"),
    ("exit_reason",     "TEXT"),
    ("notes",           "TEXT"),
]

# Everything a caller may write (id is assigned by SQLite).
FIELDS = [name for name, _ in COLUMNS if name != "id"]


def _create_sql(table):
    body = ",\n    ".join(f"{name} {decl}" for name, decl in COLUMNS)
    return f"CREATE TABLE IF NOT EXISTS {table} (\n    {body}\n)"


def connect(db_path=None):
    """Opens the database and makes sure both tables exist.

    Rows come back as sqlite3.Row, so callers can use trade["profit"]
    instead of counting tuple positions.
    """
    path = Path(db_path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    with conn:
        for table in TABLES:
            conn.execute(_create_sql(table))
    return conn


def _check_table(table):
    if table not in TABLES:
        raise ValueError(f"Unknown table '{table}'. Expected one of: {', '.join(TABLES)}")


def insert(table, rows, db_path=None):
    """Writes trades and returns their new ids. All rows go in one
    transaction: either every trade lands or none does — a half-written
    backtest run is worse than no run."""
    _check_table(table)
    rows = list(rows)
    if not rows:
        return []

    placeholders = ", ".join("?" for _ in FIELDS)
    sql = f"INSERT INTO {table} ({', '.join(FIELDS)}) VALUES ({placeholders})"

    conn = connect(db_path)
    try:
        ids = []
        with conn:  # commits on success, rolls back on any exception
            for row in rows:
                unknown = set(row) - set(FIELDS)
                if unknown:
                    raise ValueError(
                        f"Unknown field(s) for {table}: {', '.join(sorted(unknown))}. "
                        f"Allowed: {', '.join(FIELDS)}"
                    )
                cur = conn.execute(sql, [row.get(f) for f in FIELDS])
                ids.append(cur.lastrowid)
        return ids
    finally:
        conn.close()


def update(table, trade_id, values, db_path=None):
    """Changes one existing trade. Raises if that id isn't there.

    This is the guard the old journal lacked: it used pandas .loc, which
    SILENTLY INVENTED a row when handed an index that didn't exist — in the
    real-money record. Here, a bad id is an error, never a new trade.
    """
    _check_table(table)
    if not values:
        raise ValueError("Nothing to update.")
    unknown = set(values) - set(FIELDS)
    if unknown:
        raise ValueError(
            f"Unknown field(s) for {table}: {', '.join(sorted(unknown))}. "
            f"Allowed: {', '.join(FIELDS)}"
        )

    assignments = ", ".join(f"{k} = ?" for k in values)
    conn = connect(db_path)
    try:
        with conn:
            cur = conn.execute(
                f"UPDATE {table} SET {assignments} WHERE id = ?",
                [*values.values(), trade_id],
            )
            if cur.rowcount == 0:
                raise KeyError(f"No trade with id {trade_id} in {table}.")
    finally:
        conn.close()


def fetch(table, where=None, params=(), db_path=None):
    """Reads trades back as a list of dicts, oldest entry first."""
    _check_table(table)
    sql = f"SELECT * FROM {table}"
    if where:
        sql += f" WHERE {where}"
    sql += " ORDER BY entry_timestamp, id"

    conn = connect(db_path)
    try:
        return [dict(row) for row in conn.execute(sql, params)]
    finally:
        conn.close()


def delete(table, where=None, params=(), db_path=None):
    """Removes trades and returns how many went. No `where` clears the table."""
    _check_table(table)
    sql = f"DELETE FROM {table}" + (f" WHERE {where}" if where else "")
    conn = connect(db_path)
    try:
        with conn:
            return conn.execute(sql, params).rowcount
    finally:
        conn.close()
