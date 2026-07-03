"""User-activity detector using pynput global input listeners + GetLastInputInfo.

Architecture:
  Two-layer detection:
    1. pynput global hooks (low-latency, for mid-burst abort)
    2. GetLastInputInfo Win32 API (never dies, immune to synthetic input)

  A watchdog thread revives pynput listeners if they silently disconnect
  (common on sleep/resume, monitor change, or lock screen).

  A thread-local flag filters synthetic input from the simulation engine
  so the detector doesn't mistake its own simulation for user activity.
"""

import contextlib
import ctypes
import ctypes.wintypes
import logging
import threading
import time

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Win32 GetLastInputInfo — reliable, never disconnects
# ---------------------------------------------------------------------------

_HAS_WIN32_API = False
_LASTINPUTINFO: type  # forward-declare for type-checkers

try:
    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32

    class _LASTINPUTINFO(ctypes.Structure):  # type: ignore[no-redef]
        _fields_ = [
            ("cbSize", ctypes.wintypes.UINT),
            ("dwTime", ctypes.wintypes.DWORD),
        ]

    _GetLastInputInfo = _user32.GetLastInputInfo
    _GetLastInputInfo.argtypes = [ctypes.POINTER(_LASTINPUTINFO)]
    _GetLastInputInfo.restype = ctypes.c_bool

    _GetTickCount = _kernel32.GetTickCount
    _GetTickCount.restype = ctypes.wintypes.DWORD

    _HAS_WIN32_API = True
except (AttributeError, OSError):
    # Non-Windows system — GetLastInputInfo is unavailable.
    # ActivityDetector falls back to pynput listeners only.
    _GetLastInputInfo = None  # type: ignore[assignment]
    _GetTickCount = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Pynput (optional, graceful degradation)
# ---------------------------------------------------------------------------

try:
    from pynput import keyboard, mouse

    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False

    class mouse:  # type: ignore[no-redef]
        class Listener:
            def __init__(self, **kwargs):
                pass

            def start(self):
                pass

            def stop(self):
                pass

            @property
            def running(self):
                return False

    class keyboard:  # type: ignore[no-redef]
        class Listener:
            def __init__(self, **kwargs):
                pass

            def start(self):
                pass

            def stop(self):
                pass

            @property
            def running(self):
                return False

# ---------------------------------------------------------------------------
# Cross-thread synthetic-input flag (threading.Event so pynput callbacks
# in other threads can see it)
# ---------------------------------------------------------------------------

_synthetic_active = threading.Event()


def mark_synthetic(on: bool) -> None:
    """Mark (or unmark) the process as generating synthetic input.

    When set, pynput callbacks in ActivityDetector._on_input() will ignore
    events, preventing the simulation engine from detecting its own output
    as user activity.

    Uses threading.Event so the flag is visible across all threads
    (pynput runs callbacks in a different thread than the engine).
    """
    if on:
        _synthetic_active.set()
    else:
        _synthetic_active.clear()


def is_synthetic() -> bool:
    return _synthetic_active.is_set()


# ---------------------------------------------------------------------------
# ActivityDetector
# ---------------------------------------------------------------------------


class ActivityDetector:
    """Monitors global mouse and keyboard input to detect user presence.

    After *timeout* seconds of no input the user is considered idle.
    Thread-safe via a lock around the last-activity timestamp.

    Detection layers (best-of-both):
      - pynput listeners: low-latency, good for mid-burst abort
      - GetLastInputInfo: reliable Win32 API, never dies, ignores synthetic
        input from SendInput/pyautogui
    """

    def __init__(self, timeout: float = 30.0) -> None:
        self._lock = threading.Lock()
        self._timeout = timeout
        self._last_activity: float = time.time()
        self._mouse_listener: mouse.Listener | None = None
        self._keyboard_listener: keyboard.Listener | None = None
        self._running = False
        self._watchdog_thread: threading.Thread | None = None
        self._watchdog_event = threading.Event()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the global input listeners + watchdog."""
        self._last_activity = time.time()
        self._start_pynput()
        self._running = True

        if HAS_PYNPUT:
            self._watchdog_event.clear()
            self._watchdog_thread = threading.Thread(
                target=self._watchdog_loop,
                daemon=True,
                name="DetectorWatchdog",
            )
            self._watchdog_thread.start()

    def stop(self) -> None:
        """Stop all listeners and watchdog."""
        self._running = False
        self._watchdog_event.set()
        self._stop_pynput()

    def is_user_active(self) -> bool:
        """Return True if user input was detected within the timeout window.

        Uses TWO data sources and takes the MOST RECENT timestamp:
          1. Win32 GetLastInputInfo (always available, ignores synthetic input)
          2. Pynput timestamp (may include synthetic if filtering fails)

        This prevents the engine from simulating when the user is actually
        present but pynput has silently disconnected.
        """
        now = time.time()

        # --- Layer 1: Win32 API (reliable, ignores synthetic input) ---
        if _HAS_WIN32_API:
            try:
                lii = _LASTINPUTINFO()
                lii.cbSize = ctypes.sizeof(_LASTINPUTINFO)
                if _GetLastInputInfo(ctypes.byref(lii)):
                    tick_now = _GetTickCount()
                    ms_since = (tick_now - lii.dwTime) & 0xFFFFFFFF
                    # Sanity check: GetLastInputInfo wraps at ~49.7 days
                    if 0 <= ms_since < 86_400_000:  # < 24 hours
                        win32_time = now - ms_since / 1000.0
                        with self._lock:
                            if win32_time > self._last_activity:
                                self._last_activity = win32_time
            except Exception:
                pass

        # --- Layer 2: check against stored timestamp ---
        with self._lock:
            elapsed = now - self._last_activity
            return elapsed < self._timeout

    def seconds_since_last_input(self) -> float:
        """Return the number of seconds since the last detected input."""
        # Force a GetLastInputInfo update first
        self.is_user_active()
        with self._lock:
            return time.time() - self._last_activity

    # ------------------------------------------------------------------
    # Pynput lifecycle
    # ------------------------------------------------------------------

    def _start_pynput(self) -> None:
        if not HAS_PYNPUT:
            return
        self._mouse_listener = mouse.Listener(
            on_move=self._on_input,
            on_click=self._on_input,
            on_scroll=self._on_input,
        )
        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_input,
            on_release=self._on_input,
        )
        self._mouse_listener.start()
        self._keyboard_listener.start()

    def _stop_pynput(self) -> None:
        if self._mouse_listener is not None:
            with contextlib.suppress(Exception):
                self._mouse_listener.stop()
        if self._keyboard_listener is not None:
            with contextlib.suppress(Exception):
                self._keyboard_listener.stop()

    def _on_input(self, *args, **kwargs) -> None:
        """Callback fired by pynput on any mouse/keyboard event.

        Skips update if the current thread is generating synthetic input
        (set by mark_synthetic()), preventing the feedback loop where the
        engine detects its own simulation as user activity.
        """
        if is_synthetic():
            return
        with self._lock:
            self._last_activity = time.time()

    # ------------------------------------------------------------------
    # Watchdog — revive pynput listeners if they silently die
    # ------------------------------------------------------------------

    def _watchdog_loop(self) -> None:
        """Check pynput listener health every 5 seconds.

        If a listener has silently stopped (common after sleep/resume,
        monitor changes, or lock screen), restart both listeners.
        """
        while not self._watchdog_event.is_set():
            self._watchdog_event.wait(5)
            if self._watchdog_event.is_set():
                break
            if not self._running:
                break

            ml = self._mouse_listener
            kl = self._keyboard_listener

            ml_alive = ml is not None and ml.running
            kl_alive = kl is not None and kl.running

            if not ml_alive or not kl_alive:
                logger.warning(
                    "Pynput listener(s) disconnected (mouse=%s, kbd=%s) — restarting",
                    ml_alive,
                    kl_alive,
                )
                self._stop_pynput()
                self._start_pynput()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def running(self) -> bool:
        return self._running
