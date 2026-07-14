import pandas as pd
import os
from datetime import datetime

JOURNAL_PATH = "journal/trade_journal.csv"

def add_trade(pair, direction, entry_price, stop_loss, take_profit, reason, notes=""):
    """
    Logs one real (or paper) trade you actually took, with your reasoning.
    direction: "long" or "short"
    reason: why you took the trade (e.g. "MA20 crossover + support bounce")
    notes: anything else you want to remember later
    """
    trade = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "pair": pair,
        "direction": direction,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "reason": reason,
        "notes": notes,
        "outcome": "open"  # updated later once the trade closes
    }

    # If the journal file already exists, load and append.
    # If it's the very first trade ever, start a new file.
    if os.path.exists(JOURNAL_PATH):
        journal = pd.read_csv(JOURNAL_PATH)
        journal = pd.concat([journal, pd.DataFrame([trade])], ignore_index=True)
    else:
        journal = pd.DataFrame([trade])

    journal.to_csv(JOURNAL_PATH, index=False)
    print(f"Trade logged: {pair} {direction} @ {entry_price}")

def close_trade(index, exit_price, outcome_notes=""):
    """
    Marks a logged trade as closed and records the result.
    index: the row number of the trade in the journal (0, 1, 2...)
    outcome_notes: what happened / what you learned
    """
    journal = pd.read_csv(JOURNAL_PATH)
    journal.loc[index, "exit_price"] = exit_price
    journal.loc[index, "outcome"] = "closed"
    journal.loc[index, "outcome_notes"] = outcome_notes
    journal.to_csv(JOURNAL_PATH, index=False)
    print(f"Trade {index} closed at {exit_price}")

def view_journal():
    """Prints every logged trade."""
    if not os.path.exists(JOURNAL_PATH):
        print("No trades logged yet.")
        return
    journal = pd.read_csv(JOURNAL_PATH)
    print(journal.to_string())