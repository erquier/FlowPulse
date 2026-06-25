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
    "click_chance": 0.30,
    "scroll_chance": 0.20,
    "keyboard_every_n_moves": 3,
    "mouse_speed_min": 0.1,
    "mouse_speed_max": 0.6,
    "keyboard_enabled": True,
    "focus_enabled": True,  # NOTE: currently ignored (dead modules) — see engine.py
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
    "mouse_speed_min": (float, 0.1),
    "mouse_speed_max": (float, 0.6),
    "idle_timeout_sec": ((int, float), 30),
    "keyboard_every_n_moves": (int, 3),
    "log_max_bytes": (int, 1048576),
    "log_backup_count": (int, 5),
    "click_chance": (float, 0.30),
    "scroll_chance": (float, 0.20),
    "keyboard_enabled": (bool, True),
    "focus_enabled": (bool, True),  # NOTE: currently ignored (dead modules) — see engine.py
    "auto_start": (bool, False),
    "enabled": (bool, True),
}


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
                    with open(self._path, "r", encoding="utf-8") as fh:
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
            except (json.JSONDecodeError, OSError, PermissionError):
                pass
            self._loaded = True

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
        """Set a config value and persist to disk."""
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
