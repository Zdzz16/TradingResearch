"""
MA crossover — buy when Close crosses above its moving average.

--------------------------------------------------------------------------
Every .py file in this folder IS a strategy. Drop one in, refresh the
dashboard, and it appears in the picker — there is nothing to register.

The contract:

  generate_signals(data, **params)   REQUIRED
      Takes the price data (Open/High/Low/Close) and returns it with a
      boolean 'NewSignal' column: True on days a trade should be entered.
      Optionally also set 'Direction' (+1 long, -1 short), 'StopDistance',
      'TargetDistance' or 'EntryLimit' per signal — see core/engine.py.

  LABEL          optional  name shown in the picker (default: the filename)
  DESCRIPTION    optional  one line shown under the picker
  PARAMS         optional  the knobs the dashboard renders for you; each is
                           {name, label, type: int|float, default, min, max, step}
                           and arrives in generate_signals as a keyword.
  slug(params)   optional  short name used in results/ filenames

Stop loss, take profit and hold time are NOT strategy params — they belong
to the engine and the dashboard supplies them separately.
--------------------------------------------------------------------------
"""

LABEL = "MA crossover"
DESCRIPTION = "Buy when Close crosses above its moving average."

PARAMS = [
    {"name": "window", "label": "MA window", "type": "int",
     "default": 20, "min": 2, "max": 200, "step": 1},
]


def slug(params):
    """Short name for result filenames, e.g. 'ma20'."""
    return f"ma{params['window']}"


def generate_signals(data, window=20):
    """
    Flags days where Close crosses above its N-day moving average.
    Returns the full data with extra columns: MA, Signal, NewSignal.
    """
    data = data.copy()  # avoid modifying the original data by accident
    data[f"MA{window}"] = data["Close"].rolling(window=window).mean()
    data["Signal"] = data["Close"] > data[f"MA{window}"]
    prev_signal = data["Signal"].shift(1, fill_value=False)
    data["NewSignal"] = data["Signal"] & (~prev_signal)
    return data
