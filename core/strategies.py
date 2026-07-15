"""
Setup-detection logic — each strategy reads price data and marks the days
a trade should be entered (the 'NewSignal' column the engine looks for).

Adding a strategy is meant to be two steps and nothing else:
  1. write the function, taking (data, **its own params) and returning data
     with a NewSignal column;
  2. add an entry to STRATEGIES below.
The dashboard reads STRATEGIES to build its picker and its parameter
controls, so a new strategy shows up in the UI with no UI code at all.
"""


def ma_crossover(data, window=20):
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


# The registry. Each entry describes one strategy:
#   label/description — what the picker shows.
#   fn                — the function above.
#   params            — every knob the strategy owns, with its limits. The
#                       dashboard renders these; nothing about them is
#                       hardcoded in the UI. (Stop/target/hold are NOT here:
#                       those belong to the engine, not to a strategy.)
#   slug              — a short name for result filenames, e.g. "ma20".
STRATEGIES = {
    "ma_crossover": {
        "label": "MA crossover",
        "description": "Buy when Close crosses above its moving average.",
        "fn": ma_crossover,
        "slug": lambda p: f"ma{p['window']}",
        "params": [
            {"name": "window", "label": "MA window", "type": "int",
             "default": 20, "min": 2, "max": 200, "step": 1},
        ],
    },
}


def get_strategy(name):
    """Returns one strategy's config, with a helpful error if it's unknown."""
    if name not in STRATEGIES:
        raise ValueError(
            f"Unknown strategy '{name}'. Available: {', '.join(STRATEGIES)}"
        )
    return STRATEGIES[name]


def resolve_params(name, params=None):
    """Fills in each param's default for anything the caller left out, and
    casts to the declared type — the values may have arrived as JSON."""
    spec = get_strategy(name)["params"]
    given = params or {}
    out = {}
    for p in spec:
        value = given.get(p["name"], p["default"])
        if p.get("type") == "int":
            value = int(value)
        elif p.get("type") == "float":
            value = float(value)
        if "min" in p and value < p["min"]:
            raise ValueError(f"{p['label']} must be at least {p['min']}, got {value}.")
        if "max" in p and value > p["max"]:
            raise ValueError(f"{p['label']} must be at most {p['max']}, got {value}.")
        out[p["name"]] = value
    return out


def apply_strategy(data, name, params=None):
    """Runs a strategy by name. Returns (data_with_signals, resolved_params)."""
    resolved = resolve_params(name, params)
    return get_strategy(name)["fn"](data, **resolved), resolved
