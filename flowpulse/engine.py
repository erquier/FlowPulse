"""Simulation engine — human-like input bursts in a background thread."""

import logging
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from flowpulse.config import Config
from flowpulse.detector import ActivityDetector, mark_synthetic

logger = logging.getLogger(__name__)

# Try importing simulation libraries; degrade gracefully.
try:
    import pyautogui
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

    class pyautogui:  # type: ignore[no-redef]
        @staticmethod
        def moveRel(x, y, duration=0):
            pass
        @staticmethod
        def click():
            pass
        @staticmethod
        def scroll(clicks):
            pass
        @staticmethod
        def press(key):
            pass
        @staticmethod
        def typewrite(text):
            pass
        @staticmethod
        def size():
            return (1920, 1080)


@dataclass
class EngineStats:
    """Exposed simulation statistics."""
    total_moves: int = 0
    uptime_seconds: float = 0.0
    current_state: str = "stopped"  # stopped | running | idle_wait | burst | read_pause | long_pause
    bursts_completed: int = 0


class SimulationEngine:
    """Runs the simulation loop in a separate daemon thread.

    Lifecycle phases (per burst):
        burst_active  → read_pause → burst_active → … → long_pause → repeat
    """

    def __init__(self, config: Config, detector: ActivityDetector) -> None:
        self._config = config
        self._detector = detector
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._start_time: float = 0.0
        self._stats = EngineStats()
        self._stats_lock = threading.Lock()
        self._keys = "abcdefghijklmnopqrstuvwxyz ,./;'[]()-="

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the simulation thread."""
        if self.is_running():
            logger.warning("Engine already running")
            return
        self._stop_event.clear()
        self._start_time = time.time()
        self._update_state("running")
        self._thread = threading.Thread(target=self._run_loop,
                                        name="SimulationEngine",
                                        daemon=True)
        self._thread.start()
        logger.info("Simulation engine started")

    def stop(self) -> None:
        """Signal the simulation thread to stop and wait for it."""
        self._stop_event.set()
        self._update_state("stopped")
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=5)
        logger.info("Simulation engine stopped")

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def stats(self) -> EngineStats:
        """Return a snapshot of current engine statistics."""
        with self._stats_lock:
            uptime = time.time() - self._start_time if self._start_time else 0.0
            return EngineStats(
                total_moves=self._stats.total_moves,
                uptime_seconds=uptime,
                current_state=self._stats.current_state,
                bursts_completed=self._stats.bursts_completed,
            )

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        """Core simulation loop — runs until stop is requested."""
        while not self._stop_event.is_set():
            # If the user is active, wait quietly.
            if self._detector.is_user_active():
                self._update_state("idle_wait")
                self._stop_event.wait(1.0)
                continue

            # ---- Burst phase ----
            self._execute_burst()

            if self._stop_event.is_set():
                break

            # ---- Read pause (short) ----
            pause = random.uniform(
                self._config.get("read_pause_min_sec", 3),
                self._config.get("read_pause_max_sec", 12),
            )
            self._update_state("read_pause")
            logger.debug("Read pause: %.1f s", pause)
            if self._wait_with_abort(pause):
                break

            # ---- Long pause ----
            long_pause = random.uniform(
                self._config.get("long_pause_min_sec", 60),
                self._config.get("long_pause_max_sec", 300),
            )
            self._update_state("long_pause")
            logger.debug("Long pause: %.1f s", long_pause)
            if self._wait_with_abort(long_pause):
                break

    # ------------------------------------------------------------------
    # Burst execution
    # ------------------------------------------------------------------

    def _execute_burst(self) -> None:
        """Perform a single burst of 8-15 pseudo-human input actions.

        Aborts immediately if the user resumes activity mid-burst,
        preventing interference with real mouse/keyboard input.

        All synthetic input is wrapped in mark_synthetic() so the
        activity detector does not mistake its own simulation for
        real user activity.  Each pyautogui call is individually
        try/except-ed to survive a broken or disconnected library.
        """
        mark_synthetic(True)
        try:
            moves = random.randint(
                int(self._config.get("burst_min_moves", 8)),
                int(self._config.get("burst_max_moves", 15)),
            )
            self._update_state("burst")
            keyboard_every = int(self._config.get("keyboard_every_n_moves", 3))
            screen_w, screen_h = pyautogui.size()

            for i in range(moves):
                if self._stop_event.is_set():
                    return

                # --- Abort if user resumed activity mid-burst ---
                if self._detector.is_user_active():
                    logger.debug("User active mid-burst — aborting remaining %d moves", moves - i)
                    break

                # --- Mouse move (always) ---
                dx = random.randint(-150, 150)
                dy = random.randint(-150, 150)
                speed = random.uniform(
                    self._config.get("mouse_speed_min", 0.1),
                    self._config.get("mouse_speed_max", 0.6),
                )
                try:
                    pyautogui.moveRel(dx, dy, duration=speed)
                except Exception:
                    logger.error("pyautogui.moveRel failed")
                    break

                with self._stats_lock:
                    self._stats.total_moves += 1

                # --- Abort if mouse move triggered user-activity detection ---
                if self._detector.is_user_active():
                    logger.debug("User active after mouse move — aborting burst")
                    break

                # --- Click (30 % chance) ---
                if random.random() < self._config.get("click_chance", 0.30):
                    try:
                        pyautogui.click()
                    except Exception:
                        logger.error("pyautogui.click failed")
                        break
                    with self._stats_lock:
                        self._stats.total_moves += 1
                    if self._detector.is_user_active():
                        logger.debug("User active after click — aborting burst")
                        break

                # --- Scroll (20 % chance) ---
                if random.random() < self._config.get("scroll_chance", 0.20):
                    try:
                        pyautogui.scroll(random.choice([-3, -2, -1, 1, 2, 3]))
                    except Exception:
                        logger.error("pyautogui.scroll failed")
                        break
                    with self._stats_lock:
                        self._stats.total_moves += 1

                # --- Keyboard every N moves ---
                if (i + 1) % keyboard_every == 0:
                    key = random.choice(self._keys)
                    try:
                        pyautogui.press(key)
                    except Exception:
                        logger.error("pyautogui.press failed")
                        break

                # Small human-like delay between actions
                time.sleep(random.uniform(0.05, 0.35))

            with self._stats_lock:
                self._stats.bursts_completed += 1
        finally:
            mark_synthetic(False)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _wait_with_abort(self, seconds: float) -> bool:
        """Sleep for *seconds*, returning True if stop was requested.

        Also aborts early if the user resumes activity, so a long pause
        doesn't finish and start a new burst while the person is back.
        """
        deadline = time.time() + seconds
        while time.time() < deadline:
            if self._stop_event.is_set():
                return True
            if self._detector.is_user_active():
                logger.debug("User active during pause — skipping remaining %.1f s",
                             deadline - time.time())
                return False  # don't stop, just end pause early
            self._stop_event.wait(0.5)
        return False

    def _update_state(self, state: str) -> None:
        with self._stats_lock:
            self._stats.current_state = state
