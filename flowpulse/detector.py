"""User-activity detector using pynput global input listeners."""

import threading
import time
from typing import Optional

try:
    from pynput import mouse, keyboard
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False

    class mouse:  # type: ignore[no-redef]
        class Controller:
            pass

        class Listener:
            def __init__(self, **kwargs):
                pass
            def start(self):
                pass
            def stop(self):
                pass

    class keyboard:  # type: ignore[no-redef]
        class Listener:
            def __init__(self, **kwargs):
                pass
            def start(self):
                pass
            def stop(self):
                pass


class ActivityDetector:
    """Monitors global mouse and keyboard input to detect user presence.

    After *timeout* seconds of no input the user is considered idle.
    Thread-safe via a lock around the last-activity timestamp.
    """

    def __init__(self, timeout: float = 30.0) -> None:
        self._lock = threading.Lock()
        self._timeout = timeout
        self._last_activity: float = time.time()
        self._mouse_listener: Optional[mouse.Listener] = None
        self._keyboard_listener: Optional[keyboard.Listener] = None
        self._running = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the global input listeners."""
        if not HAS_PYNPUT:
            return
        if self._running:
            return
        self._last_activity = time.time()
        self._mouse_listener = mouse.Listener(on_move=self._on_input,
                                              on_click=self._on_input,
                                              on_scroll=self._on_input)
        self._keyboard_listener = keyboard.Listener(on_press=self._on_input,
                                                    on_release=self._on_input)
        self._mouse_listener.start()
        self._keyboard_listener.start()
        self._running = True

    def stop(self) -> None:
        """Stop the global input listeners."""
        if self._mouse_listener is not None:
            self._mouse_listener.stop()
        if self._keyboard_listener is not None:
            self._keyboard_listener.stop()
        self._running = False

    def is_user_active(self) -> bool:
        """Return True if user input was detected within the timeout window."""
        with self._lock:
            elapsed = time.time() - self._last_activity
            return elapsed < self._timeout

    def seconds_since_last_input(self) -> float:
        """Return the number of seconds since the last detected input."""
        with self._lock:
            return time.time() - self._last_activity

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_input(self, *args, **kwargs) -> None:
        """Callback fired by pynput on any mouse/keyboard event."""
        with self._lock:
            self._last_activity = time.time()

    @property
    def running(self) -> bool:
        return self._running
