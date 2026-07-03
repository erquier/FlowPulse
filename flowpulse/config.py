"""Configuration manager for FlowPulse."""

import json
import logging
import os
import platform
import threading
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "burst_min_moves": 8,
    "burst_max_moves": 15,
    "read_pause_min_sec": 3,
    "read_pause_max_sec": 12,
    "long_pause_min_sec": 60,
    "long_pause_max_sec": 300,
    # Long pause fires every burst_trigger_min-burst_trigger_max bursts
    # (ported from the deprecated scheduler.py's burst_trigger_range),
    # instead of after every single burst.
    "burst_trigger_min": 3,
    "burst_trigger_max": 5,
    # Gaussian-clamped delay between actions inside a burst (ported from
    # scheduler.py's next_activity_interval); replaces a flat uniform delay
    # so intra-burst pacing looks less mechanically regular.
    "move_interval_mean_sec": 0.2,
    "move_interval_sigma_sec": 0.08,
    "move_interval_min_sec": 0.05,
    "move_interval_max_sec": 0.35,
    "click_chance": 0.30,
    "scroll_chance": 0.20,
    "keyboard_every_n_moves": 3,
    "mouse_speed_min": 0.1,
    "mouse_speed_max": 0.6,
    "keyboard_enabled": True,
    "focus_enabled": True,  # NOTE: now active — see engine.py focus_rotate() call
    "auto_start": False,
    "idle_timeout_sec": 30,
    "log_level": "INFO",
    "log_max_bytes": 1048576,
    "log_backup_count": 5,
    "enabled": True,
}

_CONFIG_SCHEMA: dict[str, tuple] = {
    "burst_min_moves": (int, 8),
    "burst_max_moves": (int, 15),
    "read_pause_min_sec": ((int, float), 3),
    "read_pause_max_sec": ((int, float), 12),
    "long_pause_min_sec": ((int, float), 60),
    "long_pause_max_sec": ((int, float), 300),
    "burst_trigger_min": (int, 3),
    "burst_trigger_max": (int, 5),
    "move_interval_mean_sec": ((int, float), 0.2),
    "move_interval_sigma_sec": ((int, float), 0.08),
    "move_interval_min_sec": ((int, float), 0.05),
    "move_interval_max_sec": ((int, float), 0.35),
    "mouse_speed_min": (float, 0.1),
    "mouse_speed_max": (float, 0.6),
    "idle_timeout_sec": ((int, float), 30),
    "keyboard_every_n_moves": (int, 3),
    "log_max_bytes": (int, 1048576),
    "log_backup_count": (int, 5),
    "click_chance": (float, 0.30),
    "scroll_chance": (float, 0.20),
    "keyboard_enabled": (bool, True),
    "focus_enabled": (bool, True),  # NOTE: now active — see engine.py focus_rotate() call
    "auto_start": (bool, False),
    "enabled": (bool, True),
}

# Inclusive (min, max) bounds for numeric keys. Keys with no meaningful
# range (bools, log_level) are omitted.
_BOUNDS: dict[str, tuple[float, float]] = {
    "burst_min_moves": (1, 1000),
    "burst_max_moves": (1, 1000),
    "read_pause_min_sec": (0, 3600),
    "read_pause_max_sec": (0, 3600),
    "long_pause_min_sec": (0, 86400),
    "long_pause_max_sec": (0, 86400),
    "burst_trigger_min": (1, 1000),
    "burst_trigger_max": (1, 1000),
    "move_interval_mean_sec": (0, 60),
    "move_interval_sigma_sec": (0, 60),
    "move_interval_min_sec": (0, 60),
    "move_interval_max_sec": (0, 60),
    "mouse_speed_min": (0.01, 10),
    "mouse_speed_max": (0.01, 10),
    "idle_timeout_sec": (0, 86400),
    "keyboard_every_n_moves": (1, 1000),
    "log_max_bytes": (1024, 1_073_741_824),
    "log_backup_count": (0, 100),
    "click_chance": (0.0, 1.0),
    "scroll_chance": (0.0, 1.0),
}

# (min_key, max_key) pairs that must satisfy config[min_key] <= config[max_key].
# Checked only in load() against the fully-merged config, not in set():
# the settings dialog calls set() once per field in sequence, so eagerly
# rejecting a single-field update based on the *other* field's current
# value would spuriously fail legitimate edits (e.g. raising both bounds
# of a pair, where the new min briefly exceeds the still-old max).
_ORDERED_PAIRS: list[tuple[str, str]] = [
    ("burst_min_moves", "burst_max_moves"),
    ("read_pause_min_sec", "read_pause_max_sec"),
    ("long_pause_min_sec", "long_pause_max_sec"),
    ("burst_trigger_min", "burst_trigger_max"),
    ("move_interval_min_sec", "move_interval_max_sec"),
    ("mouse_speed_min", "mouse_speed_max"),
]


def _get_config_dir() -> str:
    """Return the platform-appropriate config directory."""
    if platform.system() == "Windows":
        base = os.environ.get("APPDATA", os.path.expanduser("~\\AppData\\Roaming"))
    else:
        base = os.path.expanduser("~")
    return os.path.join(base, ".flowpulse")


def _get_config_path() -> str:
    """Return the full path to the config JSON file."""
    return os.path.join(_get_config_dir(), "config.json")


class Config:
    """Thread-safe JSON configuration manager for FlowPulse."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._path = _get_config_path()
        self._data: dict[str, Any] = dict(DEFAULT_CONFIG)
        self._loaded = False
        os.makedirs(_get_config_dir(), exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load configuration from disk, falling back to defaults."""
        with self._lock:
            self._data = dict(DEFAULT_CONFIG)
            try:
                if os.path.isfile(self._path):
                    with open(self._path, encoding="utf-8") as fh:
                        stored = json.load(fh)
                    if isinstance(stored, dict):
                        self._data.update(stored)
                        # Validate each key against schema; reset bad typed values
                        for key, (expected_type, default) in _CONFIG_SCHEMA.items():
                            value = self._data.get(key, default)
                            if not isinstance(value, expected_type):
                                logger.warning(
                                    "Config key '%s' has wrong type %s (expected %s), "
                                    "resetting to default %r",
                                    key,
                                    type(value).__name__,
                                    expected_type,
                                    default,
                                )
                                self._data[key] = default
                        self._enforce_bounds_locked()
                        self._enforce_ordered_pairs_locked()
            except (json.JSONDecodeError, OSError, PermissionError):
                pass
            self._loaded = True

    def _enforce_bounds_locked(self) -> None:
        """Reset any key outside its allowed range to the schema default.

        Caller must hold self._lock. Bool/non-numeric keys have no entry
        in _BOUNDS and are skipped.
        """
        for key, (lo, hi) in _BOUNDS.items():
            value = self._data.get(key)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                continue
            if not (lo <= value <= hi):
                default = _CONFIG_SCHEMA[key][1]
                logger.warning(
                    "Config key '%s' value %r out of range [%s, %s], resetting to default %r",
                    key,
                    value,
                    lo,
                    hi,
                    default,
                )
                self._data[key] = default

    def _enforce_ordered_pairs_locked(self) -> None:
        """Reset both keys of a pair to their defaults if min > max.

        Caller must hold self._lock.
        """
        for min_key, max_key in _ORDERED_PAIRS:
            lo = self._data.get(min_key)
            hi = self._data.get(max_key)
            if not isinstance(lo, (int, float)) or not isinstance(hi, (int, float)):
                continue
            if lo > hi:
                lo_default = _CONFIG_SCHEMA[min_key][1]
                hi_default = _CONFIG_SCHEMA[max_key][1]
                logger.warning(
                    "Config '%s' (%r) > '%s' (%r), resetting both to defaults (%r, %r)",
                    min_key,
                    lo,
                    max_key,
                    hi,
                    lo_default,
                    hi_default,
                )
                self._data[min_key] = lo_default
                self._data[max_key] = hi_default

    def save(self) -> None:
        """Persist current configuration to disk."""
        with self._lock:
            tmp = str(self._path) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, ensure_ascii=False)
            os.replace(tmp, self._path)

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a config value by key."""
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a config value and persist to disk.

        Raises ValueError if *key* has a known numeric range (see
        _BOUNDS) and *value* falls outside it. Cross-field ordering
        (e.g. burst_min_moves <= burst_max_moves) is intentionally not
        checked here -- see _ORDERED_PAIRS' docstring note -- only
        enforced in load().
        """
        bounds = _BOUNDS.get(key)
        if bounds is not None and isinstance(value, (int, float)) and not isinstance(value, bool):
            lo, hi = bounds
            if not (lo <= value <= hi):
                raise ValueError(f"'{key}' must be between {lo} and {hi}, got {value!r}")
        with self._lock:
            self._data[key] = value
        self.save()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @property
    def data(self) -> dict[str, Any]:
        """Return a shallow copy of the full config dict."""
        with self._lock:
            return dict(self._data)

    @property
    def path(self) -> str:
        """Path to the config file on disk."""
        return str(self._path)

    def __repr__(self) -> str:
        return f"Config(path={self._path!r}, loaded={self._loaded})"
