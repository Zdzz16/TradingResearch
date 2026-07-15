"""
Strategy discovery.

Strategies are plain Python files in the /strategies folder at the project
root — one file, one strategy. This module finds them, checks they honour
the contract, and hands them to the rest of the platform. Nothing is
registered by hand, so adding a strategy never means editing this file.
See strategies/ma_crossover.py for the contract.

Two deliberate choices:
  * The folder is re-scanned on every call, so a new strategy file appears
    in the dashboard on a refresh — no server restart.
  * A file that fails to import is skipped and recorded in load_errors
    rather than raising, so one typo in one strategy can't blank the whole
    picker. The error is surfaced in the UI instead of failing silently.
"""

import importlib.util
from pathlib import Path

STRATEGIES_DIR = Path(__file__).resolve().parent.parent / "strategies"

# name -> "ErrorType: message" for files that wouldn't load. Rewritten on
# every load_strategies() call; read it right after one.
load_errors = {}


def _load_module(path):
    """Imports a strategy file directly, without it needing to be a package
    or live on sys.path. Not cached in sys.modules, which is what lets an
    edited file take effect on the next scan."""
    spec = importlib.util.spec_from_file_location(f"_strategy_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_strategies():
    """Scans /strategies and returns {name: config}, fresh each call.
    `name` is the filename without .py — that's the strategy's id."""
    registry = {}
    load_errors.clear()
    if not STRATEGIES_DIR.is_dir():
        return registry

    for path in sorted(STRATEGIES_DIR.glob("*.py")):
        if path.stem.startswith("_"):
            continue  # _helpers.py and friends aren't strategies
        try:
            module = _load_module(path)
            fn = getattr(module, "generate_signals", None)
            if not callable(fn):
                raise AttributeError(
                    "missing a generate_signals(data, **params) function"
                )
            registry[path.stem] = {
                "label": getattr(module, "LABEL", path.stem.replace("_", " ").capitalize()),
                "description": getattr(module, "DESCRIPTION", ""),
                "params": getattr(module, "PARAMS", []),
                "fn": fn,
                "slug": getattr(module, "slug", None),
            }
        except Exception as exc:
            # one bad file shouldn't take the others down with it
            load_errors[path.stem] = f"{type(exc).__name__}: {exc}"
    return registry


def get_strategy(name):
    """One strategy's config, with an error that says what went wrong —
    unknown name, or a file that's there but broken."""
    strategies = load_strategies()
    if name in strategies:
        return strategies[name]
    if name in load_errors:
        raise ValueError(f"Strategy '{name}' failed to load — {load_errors[name]}")
    known = ", ".join(strategies) or "none found"
    raise ValueError(f"Unknown strategy '{name}'. Available: {known}")


def _resolve(cfg, params=None):
    """Fills in each param's default for anything the caller left out, casts
    to the declared type (values may have arrived as JSON), and enforces the
    declared limits."""
    given = params or {}
    out = {}
    for p in cfg["params"]:
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


def resolve_params(name, params=None):
    return _resolve(get_strategy(name), params)


def strategy_slug(name, resolved):
    """Short name for result filenames. A strategy can define its own slug();
    otherwise we build one from its params."""
    cfg = get_strategy(name)
    if callable(cfg.get("slug")):
        return cfg["slug"](resolved)
    tail = "-".join(f"{k}{v}" for k, v in sorted(resolved.items()))
    return f"{name}-{tail}" if tail else name


def apply_strategy(data, name, params=None):
    """Runs a strategy by name. Returns (data_with_signals, resolved_params)."""
    cfg = get_strategy(name)
    resolved = _resolve(cfg, params)
    return cfg["fn"](data, **resolved), resolved
