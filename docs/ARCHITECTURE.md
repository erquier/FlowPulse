# FlowPulse Architecture

## Module map

| Module | Responsibility |
|---|---|
| `FlowPulse.py` | Entry point wrapper — adds the package directory to `sys.path`, calls `flowpulse.app.main()`. Exists so Nuitka has a flat, top-level script to compile. |
| `flowpulse/app.py` | Tray icon + Windows message loop (via `pywin32`'s `win32gui`/`win32con`/`win32api`), tkinter settings dialog, CLI entry point (`--dry-run`). |
| `flowpulse/engine.py` | `SimulationEngine` — the burst/pause simulation loop, including the activity-scheduling logic described below. |
| `flowpulse/detector.py` | `ActivityDetector` — two-layer user-presence detection (see below). |
| `flowpulse/input_sim.py` | Thin `pyautogui` wrapper for mouse/keyboard actions (`mouse_move_to`, `mouse_click`, `mouse_scroll`, `keyboard_f13`, `keyboard_modifier`, `safe_coords`). |
| `flowpulse/movement.py` | Pure math: cubic Bezier path generation, easing, overshoot, tremor, Gaussian jitter. No I/O, no Win32, no `pyautogui` — fully unit-testable. |
| `flowpulse/window_focus.py` | Window enumeration and focus rotation (`rotate`, `switch_to_window`), built on `win32_api`. |
| `flowpulse/win32_api.py` | Shared raw-`ctypes` Win32 bindings used by `detector.py` and `window_focus.py` — one `HAS_WIN32` flag, lazy bindings to `user32`/`kernel32`. See "Why two Windows API layers" below. |
| `flowpulse/config.py` | `Config` — thread-safe JSON-backed settings with schema-driven type/bounds validation. |
| `tests/test_all.py` | Unit tests (`unittest`), mocking `pyautogui`/`pynput`/Win32 calls as needed. |
| `smoke_test.py` | End-to-end sanity check of the pure-logic pieces (scheduling, movement, config) without touching real input/UI — runs in CI on Ubuntu under `xvfb-run`. |

## Why two Windows API layers

`win32_api.py` (raw `ctypes`) and `app.py` (`pywin32`) both talk to Windows,
but deliberately don't share code:

- **`win32_api.py`** covers `GetLastInputInfo`/`GetTickCount`/`EnumWindows`/
  `SetForegroundWindow` — low-level, narrowly-scoped calls needed by
  `detector.py` and `window_focus.py`. Raw `ctypes` keeps these importable
  on non-Windows platforms (the whole binding block is wrapped in
  `try/except (AttributeError, OSError)`, so `HAS_WIN32` is simply `False`
  elsewhere), which matters because `smoke_test.py` and the unit tests run
  on Ubuntu in CI.
- **`app.py`** uses `pywin32` (`win32gui`/`win32con`/`win32api`) for the tray
  icon and window message loop — a fundamentally Windows-only concern with
  no cross-platform fallback path, so there's no importability constraint
  driving a raw-`ctypes` implementation here. `pywin32` is also just a
  better fit for the volume of Win32 surface area a tray app needs
  (window classes, `Shell_NotifyIcon`, popup menus, message dispatch).

Combining both under one module would mix two different API access
strategies for no real benefit — `app.py` is the only consumer of its own
calls, so there's no duplication to eliminate there.

## Two-layer activity detection

`ActivityDetector.is_user_active()` combines two independent signals and
takes whichever reports more recent activity:

1. **`pynput` global listeners** (mouse/keyboard hooks) — low latency, used
   to abort a burst quickly if the real user resumes activity mid-burst.
   Runs in a background thread; a watchdog thread (`_watchdog_loop`) checks
   every 5 seconds whether the listeners are still alive and restarts them
   if not (pynput listeners can silently die on sleep/resume, monitor
   changes, or the lock screen).
2. **`GetLastInputInfo`** (via `win32_api.milliseconds_since_last_input()`)
   — a Win32 API that never disconnects and, critically, reports the same
   value regardless of whether the input came from a real device or
   `SendInput`/`pyautogui`-style synthetic input *unless* the calling
   process itself generated it (see synthetic-input filtering below). It
   exists specifically to catch the case where pynput's listeners have
   silently died: without this layer, the engine could keep simulating
   activity while a real user is actually back at the keyboard.

Neither layer alone is sufficient: pynput is fast but fragile; Win32 is
reliable but, used alone, doesn't give the sub-second responsiveness needed
to abort a burst as soon as the user touches the mouse.

**Synthetic-input filtering**: `mark_synthetic(True)` (set for the duration
of `SimulationEngine._execute_burst()`) makes `_on_input()` ignore pynput
callbacks, so the engine's own simulated mouse/keyboard events aren't
mistaken for real user activity — this is what prevents a feedback loop
where the engine "sees" its own input and never re-enters idle/burst logic
correctly.

## Activity scheduling (humanization)

`SimulationEngine` decides *when* and *how fast* to act using logic ported
from a since-removed `scheduler.py` module (see git history around
2026-07 for the full "why" — the short version: `engine.py`'s burst loop
had drifted into a simpler reimplementation that dropped three things worth
keeping):

- **Time-of-day factor** (`_time_of_day_factor`): 1.0 during 08:00-11:00 and
  14:00-17:00, 0.3 during the 12:00-14:00 lunch dip, 0.15 otherwise. Used
  two ways: as a floor (`_active_now`, currently a no-op in practice since
  even the 0.15 off-hours value clears the 0.1 threshold) and, more
  significantly, to scale the intra-burst action interval — activity gets
  visibly slower off-hours/at lunch rather than switching on/off abruptly.
- **Gaussian-clamped intra-burst interval** (`_next_activity_interval`):
  replaces a flat `random.uniform` delay between actions inside a burst
  with a clamped Gaussian sample (Box-Muller), scaled by the time-of-day
  factor. A flat uniform distribution is comparatively easy to fingerprint
  as non-human; a peaked, time-varying one is not.
- **Burst-triggered long pauses** (`_next_pause_seconds` /
  `_roll_bursts_until_long`): a long pause fires every N bursts (N re-rolled
  each time from `burst_trigger_min`/`burst_trigger_max`), not after *every*
  burst — modeling something closer to "a few minutes of activity, a short
  break, repeat, then occasionally a longer break" rather than a
  rigid burst/rest/burst/rest cadence.

All of the above are configurable — see
[docs/CONFIGURATION.md](CONFIGURATION.md).
