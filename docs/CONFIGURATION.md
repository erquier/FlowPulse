# Configuration reference

FlowPulse's settings live in a JSON file at `%APPDATA%\.flowpulse\config.json`
(Windows) or `~/.flowpulse/config.json` (other platforms), managed by
`flowpulse/config.py`'s `Config` class. Every key below is validated on
load (wrong type or out-of-range → reset to default, logged as a warning)
and on `Config.set()` (out-of-range → raises `ValueError`); see
`_CONFIG_SCHEMA`/`_BOUNDS`/`_ORDERED_PAIRS` in `config.py` for the
authoritative source.

Bounds are enforced as a safety net against corrupted files and obviously
invalid input, not as a suggestion for reasonable values — the "Default"
column is a better guide to normal usage than the edges of "Valid range".

## Burst sizing

| Key | Type | Default | Valid range | Effect |
|---|---|---|---|---|
| `burst_min_moves` | int | 8 | 1-1000 | Minimum number of actions (moves/clicks/scrolls/keypresses) per burst. Must be ≤ `burst_max_moves` (enforced on load; see note below). |
| `burst_max_moves` | int | 15 | 1-1000 | Maximum number of actions per burst. |
| `keyboard_every_n_moves` | int | 3 | 1-1000 | A keypress fires every Nth move within a burst (if `keyboard_enabled`). |
| `click_chance` | float | 0.30 | 0.0-1.0 | Probability of a click after each move. |
| `scroll_chance` | float | 0.20 | 0.0-1.0 | Probability of a scroll after each move. |

## Pauses between bursts

| Key | Type | Default | Valid range | Effect |
|---|---|---|---|---|
| `read_pause_min_sec` | number | 3 | 0-3600 | Minimum short pause (seconds) after a burst. Must be ≤ `read_pause_max_sec`. |
| `read_pause_max_sec` | number | 12 | 0-3600 | Maximum short pause after a burst. |
| `long_pause_min_sec` | number | 60 | 0-86400 | Minimum long pause (seconds), taken every `burst_trigger_min`-`burst_trigger_max` bursts instead of a short one. Must be ≤ `long_pause_max_sec`. |
| `long_pause_max_sec` | number | 300 | 0-86400 | Maximum long pause. |
| `burst_trigger_min` | int | 3 | 1-1000 | Lower bound on how many bursts happen before a long pause (re-rolled each time). Must be ≤ `burst_trigger_max`. |
| `burst_trigger_max` | int | 5 | 1-1000 | Upper bound on the same. |

## Intra-burst pacing

Gaussian-clamped delay between individual actions within a burst — see
[ARCHITECTURE.md](ARCHITECTURE.md#activity-scheduling-humanization) for why
this replaced a flat `random.uniform` delay.

| Key | Type | Default | Valid range | Effect |
|---|---|---|---|---|
| `move_interval_mean_sec` | number | 0.2 | 0-60 | Gaussian mean of the delay between actions, before time-of-day scaling. |
| `move_interval_sigma_sec` | number | 0.08 | 0-60 | Gaussian standard deviation of that delay. |
| `move_interval_min_sec` | number | 0.05 | 0-60 | Clamp floor. Must be ≤ `move_interval_max_sec`. |
| `move_interval_max_sec` | number | 0.35 | 0-60 | Clamp ceiling. |

The effective interval is divided by the current time-of-day factor
(1.0 during typical work hours, 0.3 at lunch, 0.15 otherwise), so pacing
slows down off-hours rather than switching on/off abruptly.

## Feature toggles

| Key | Type | Default | Valid range | Effect |
|---|---|---|---|---|
| `enabled` | bool | true | n/a | Master on/off switch for the simulation loop. When false, the engine idles without acting. |
| `keyboard_enabled` | bool | true | n/a | Whether keypresses fire during a burst (see `keyboard_every_n_moves`). |
| `focus_enabled` | bool | true | n/a | Whether the engine rotates window focus after each burst (`window_focus.rotate()`). |
| `auto_start` | bool | false | n/a | Whether the simulation engine starts automatically when the app launches. |
| `idle_timeout_sec` | number | 30 | 0-86400 | Seconds of no detected user input before `ActivityDetector.is_user_active()` reports the user as idle. |

## Not currently wired up

| Key | Type | Default | Valid range |
|---|---|---|---|
| `mouse_speed_min` | float | 0.1 | 0.01-10 |
| `mouse_speed_max` | float | 0.6 | 0.01-10 |

These appear in the settings dialog and are validated/persisted like any
other key, but nothing in `engine.py`, `input_sim.py`, or `movement.py`
currently reads them — actual mouse movement speed is derived purely from
distance in `movement.py`'s `bezier_move()`/`generate_path()`. Changing
these sliders has no observable effect today. Documented here so it's a
known gap rather than a mystery; wiring them up (or removing them from the
UI) is a reasonable follow-up.

## Logging

| Key | Type | Default | Valid range | Effect |
|---|---|---|---|---|
| `log_level` | str | `"INFO"` | n/a | Passed to `logging.getLevelName()`; controls verbosity of `%APPDATA%\FlowPulse\logs\flowpulse.log`. |
| `log_max_bytes` | int | 1048576 | 1024-1073741824 | Log file size (bytes) before rotation. |
| `log_backup_count` | int | 5 | 0-100 | Number of rotated log files to keep. |

## Cross-field ordering

`burst_min_moves`/`burst_max_moves`, `read_pause_min_sec`/`read_pause_max_sec`,
`long_pause_min_sec`/`long_pause_max_sec`, `burst_trigger_min`/`burst_trigger_max`,
`move_interval_min_sec`/`move_interval_max_sec`, and
`mouse_speed_min`/`mouse_speed_max` are each checked as ordered pairs
(`min <= max`) when the config file is loaded — an inverted pair resets
*both* keys in that pair to their defaults, logged as a warning.

This check runs only in `Config.load()`, not in `Config.set()`: the
settings dialog calls `set()` once per field in sequence, so validating a
field against its pair partner's *current* (possibly not-yet-updated)
value would reject legitimate edits that happen to cross the old value
mid-update (e.g. raising both ends of a range). `Config.set()` still
validates each field's own bounds independently and raises `ValueError`
immediately if a single value is out of range.
