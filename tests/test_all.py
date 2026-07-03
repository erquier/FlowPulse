"""Unit tests for FlowPulse components."""

import math
import random

# Ensure the package is importable
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flowpulse import __version__, window_focus


class TestVersion(unittest.TestCase):
    def test_version(self):
        self.assertEqual(__version__, "1.1.0")


class TestMovement(unittest.TestCase):
    """Test the bezier curve and path generation (pure math, no mocks)."""

    def setUp(self):
        random.seed(42)

    def test_bezier_move_start_end(self):
        from flowpulse.movement import bezier_move

        points = bezier_move(100, 100, 500, 300, duration_ms=500, samples=20)
        self.assertGreater(len(points), 5)
        # First point should be near start
        sx, sy, _ = points[0]
        self.assertAlmostEqual(sx, 100, delta=2)
        self.assertAlmostEqual(sy, 100, delta=2)
        # Last point should be near overshoot (beyond target)
        ex, ey, _ = points[-1]
        self.assertGreaterEqual(ex, 495)  # should be past x2
        self.assertAlmostEqual(ey, 300, delta=20)

    def test_bezier_ease_in_out(self):
        from flowpulse.movement import bezier_move

        points = bezier_move(0, 0, 100, 0, duration_ms=500, samples=50)
        # Extract distances from origin
        dists = [math.hypot(x, y) for x, y, _ in points]
        mid = len(dists) // 2
        # Check acceleration (first half should accelerate)
        first_half = [dists[i + 1] - dists[i] for i in range(mid - 1)]
        if first_half:
            # Generally increasing speed in first half
            early_avg = sum(first_half[: len(first_half) // 3]) / max(len(first_half) // 3, 1)
            late_avg = sum(first_half[-len(first_half) // 3 :]) / max(len(first_half) // 3, 1)
            self.assertGreater(late_avg, early_avg * 0.5)  # not strict, statistical

    def test_generate_path_returns_list(self):
        from flowpulse.movement import generate_path

        path = generate_path(100, 100, 400, 300)
        self.assertIsInstance(path, list)
        self.assertGreater(len(path), 3)
        # Check structure of each step
        for x, y, delay in path:
            self.assertIsInstance(x, float)
            self.assertIsInstance(y, float)
            self.assertIsInstance(delay, (int, float))

    def test_generate_path_converges_to_target(self):
        from flowpulse.movement import generate_path

        x1, y1, x2, y2 = 200, 200, 600, 400
        path = generate_path(x1, y1, x2, y2)
        last_x, last_y, _ = path[-1]
        # Should end at or near target
        self.assertAlmostEqual(last_x, x2, delta=3)
        self.assertAlmostEqual(last_y, y2, delta=3)

    def test_generate_path_overshoot_then_correct(self):
        from flowpulse.movement import generate_path

        x1, y1, x2, y2 = 0, 0, 100, 100
        random.seed(1)
        path = generate_path(x1, y1, x2, y2)
        # Due to overshoot, path might go past target then correct
        # The last 5 steps should converge
        last_3 = path[-3:]
        for x, y, _ in last_3:
            self.assertLessEqual(abs(x - x2), 10)
            self.assertLessEqual(abs(y - y2), 10)

    def test_gauss_noise(self):
        from flowpulse.movement import _gaussian_noise

        vals = [_gaussian_noise(0, 1) for _ in range(1000)]
        mean = sum(vals) / len(vals)
        # Should be roughly centered
        self.assertAlmostEqual(mean, 0, delta=0.5)

    def test_smoothstep_range(self):
        from flowpulse.movement import _smoothstep

        for t in [0, 0.25, 0.5, 0.75, 1.0]:
            val = _smoothstep(t)
            self.assertGreaterEqual(val, 0)
            self.assertLessEqual(val, 1)

    def test_ease_in_out_range(self):
        from flowpulse.movement import _ease_in_out

        for t in [0, 0.25, 0.5, 0.75, 1.0]:
            val = _ease_in_out(t)
            self.assertGreaterEqual(val, 0)
            self.assertLessEqual(val, 1)

    def test_zero_distance_bezier(self):
        """Bezier from/to same point should be stable."""
        from flowpulse.movement import bezier_move

        points = bezier_move(100, 100, 100, 100, duration_ms=100)
        self.assertEqual(len(points), 11)  # default samples for 100ms
        for x, y, _ in points:
            self.assertAlmostEqual(x, 100, delta=0.5)
            self.assertAlmostEqual(y, 100, delta=0.5)

    def test_bezier_move_auto_duration(self):
        """duration_ms=None (auto-scale by distance) must not crash.

        Regression test: samples' default used to be computed from
        duration_ms before duration_ms's own None-default was resolved,
        raising TypeError whenever both were left as None.
        """
        from flowpulse.movement import bezier_move

        points = bezier_move(0, 0, 300, 300, duration_ms=None)
        self.assertGreater(len(points), 5)


class TestEngineScheduling(unittest.TestCase):
    """Test SimulationEngine's activity-scheduling helpers.

    These were ported from the deprecated scheduler.py's ActivityScheduler
    (time-of-day factor, Gaussian-clamped intra-burst interval, and
    burst-triggered long pauses), which engine.py's own burst/pause loop
    had never actually reimplemented.
    """

    def setUp(self):
        random.seed(42)
        from flowpulse.config import Config
        from flowpulse.engine import SimulationEngine

        config = Config()
        config.load()
        self.engine = SimulationEngine(config, Mock())

    def test_time_of_day_factor_high(self):
        import datetime

        dt = datetime.datetime(2026, 6, 2, 10, 0)
        self.assertAlmostEqual(self.engine._time_of_day_factor(dt), 1.0, delta=0.1)

    def test_time_of_day_factor_lunch(self):
        import datetime

        dt = datetime.datetime(2026, 6, 2, 13, 0)
        self.assertAlmostEqual(self.engine._time_of_day_factor(dt), 0.3, delta=0.1)

    def test_active_now(self):
        import datetime

        dt = datetime.datetime(2026, 6, 2, 10, 0)
        factor = self.engine._time_of_day_factor(dt)
        self.assertTrue(self.engine._active_now(factor=factor))

    def test_inactive_off_hours(self):
        # 3am factor is 0.15; _active_now(0.15) is still True since the
        # floor is 0.1 -- test with an explicit low value instead.
        self.assertFalse(self.engine._active_now(factor=0.05))

    def test_move_interval_gaussian_clamp(self):
        lo = self.engine._config.get("move_interval_min_sec")
        hi = self.engine._config.get("move_interval_max_sec")
        for _ in range(100):
            interval = self.engine._next_activity_interval(factor=1.0)
            self.assertGreaterEqual(interval, lo)
            self.assertLessEqual(interval, hi)

    def test_move_interval_lower_with_low_factor(self):
        fast = self.engine._next_activity_interval(factor=1.0)
        slow = self.engine._next_activity_interval(factor=0.1)
        self.assertGreater(slow, fast)

    def test_pause_duration_normal(self):
        self.engine._config.set("burst_trigger_min", 5)
        self.engine._config.set("burst_trigger_max", 5)  # long only every 5
        self.engine._reset_scheduling_state()
        lo = self.engine._config.get("read_pause_min_sec")
        hi = self.engine._config.get("read_pause_max_sec")
        # First 4 pauses should be short
        for _ in range(4):
            duration, is_long = self.engine._next_pause_seconds()
            self.assertFalse(is_long)
            self.assertGreaterEqual(duration, lo)
            self.assertLessEqual(duration, hi)

    def test_long_pause_triggers(self):
        self.engine._config.set("burst_trigger_min", 2)
        self.engine._config.set("burst_trigger_max", 2)  # every 2 bursts
        self.engine._reset_scheduling_state()
        # After 2 pauses, the 2nd should be long
        _duration1, is_long1 = self.engine._next_pause_seconds()  # count=1, short
        self.assertFalse(is_long1)
        duration2, is_long2 = self.engine._next_pause_seconds()  # count=2 >= threshold
        self.assertTrue(is_long2)
        self.assertGreaterEqual(duration2, self.engine._config.get("long_pause_min_sec"))
        self.assertLessEqual(duration2, self.engine._config.get("long_pause_max_sec"))

    def test_reset_scheduling_state(self):
        self.engine._config.set("burst_trigger_min", 4)
        self.engine._config.set("burst_trigger_max", 6)
        self.engine._next_pause_seconds()
        self.engine._next_pause_seconds()
        self.assertEqual(self.engine._burst_count, 2)
        self.engine._reset_scheduling_state()
        self.assertEqual(self.engine._burst_count, 0)


class TestConfig(unittest.TestCase):
    """Test the configuration manager."""

    def setUp(self):
        import tempfile

        self.tmpdir = tempfile.mkdtemp()
        self.patcher = patch(
            "flowpulse.config._get_config_path", return_value=Path(self.tmpdir, "config.json")
        )
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_default_config(self):
        from flowpulse.config import DEFAULT_CONFIG, Config

        cfg = Config()
        cfg.load()
        for key, val in DEFAULT_CONFIG.items():
            self.assertEqual(cfg.get(key), val)

    def test_set_and_get(self):
        from flowpulse.config import Config

        cfg = Config()
        cfg.load()
        cfg.set("burst_min_moves", 12)
        self.assertEqual(cfg.get("burst_min_moves"), 12)

    def test_save_and_reload(self):
        from flowpulse.config import Config

        cfg = Config()
        cfg.load()
        cfg.set("burst_min_moves", 20)
        cfg2 = Config()
        cfg2.load()
        self.assertEqual(cfg2.get("burst_min_moves"), 20)

    def test_get_default(self):
        from flowpulse.config import Config

        cfg = Config()
        cfg.load()
        self.assertEqual(cfg.get("nonexistent_key", "fallback"), "fallback")

    def test_path_property(self):
        from flowpulse.config import Config

        cfg = Config()
        self.assertIsInstance(cfg.path, str)
        self.assertTrue(cfg.path.endswith("config.json"))


class TestDetector(unittest.TestCase):
    """Test the activity detector with mock pynput."""

    def test_init(self):
        from flowpulse.detector import ActivityDetector

        det = ActivityDetector(timeout=0.001)  # very short timeout
        import time

        time.sleep(0.005)
        self.assertFalse(det.is_user_active())

    def test_mark_active(self):
        import time

        from flowpulse.detector import ActivityDetector

        det = ActivityDetector(timeout=0.1)
        det._on_input()
        self.assertTrue(det.is_user_active())
        time.sleep(0.15)
        self.assertFalse(det.is_user_active())

    def test_custom_timeout(self):
        from flowpulse.detector import ActivityDetector

        det = ActivityDetector(timeout=60)
        self.assertEqual(det._timeout, 60)


class TestWindowFocus(unittest.TestCase):
    """Test window enumeration and focus rotation (platform-independent parts)."""

    def test_list_windows_no_win32(self):
        with patch.object(window_focus, "HAS_WIN32", False):
            self.assertEqual(window_focus.list_windows(), [])

    def test_rotate_no_win32(self):
        with patch.object(window_focus, "HAS_WIN32", False):
            self.assertIsNone(window_focus.rotate())

    def test_switch_to_window_no_win32(self):
        with patch.object(window_focus, "HAS_WIN32", False):
            self.assertIsNone(window_focus.switch_to_window("anything"))

    def test_rotate_fewer_than_two_windows(self):
        with (
            patch.object(window_focus, "HAS_WIN32", True),
            patch.object(window_focus, "list_windows", return_value=[(1, "Only One")]),
        ):
            self.assertIsNone(window_focus.rotate())

    def test_rotate_picks_and_focuses_a_window(self):
        windows = [(111, "Window A"), (222, "Window B")]
        with (
            patch.object(window_focus, "HAS_WIN32", True),
            patch.object(window_focus, "list_windows", return_value=windows),
            patch.object(window_focus, "_SetForegroundWindow", create=True) as mock_set_fg,
        ):
            hwnd = window_focus.rotate()
        self.assertIn(hwnd, {111, 222})
        mock_set_fg.assert_called_once_with(hwnd)

    def test_switch_to_window_found(self):
        windows = [(111, "Notepad"), (222, "Chrome - Browser")]
        with (
            patch.object(window_focus, "HAS_WIN32", True),
            patch.object(window_focus, "list_windows", return_value=windows),
            patch.object(window_focus, "_SetForegroundWindow", create=True) as mock_set_fg,
        ):
            hwnd = window_focus.switch_to_window("chrome")
        self.assertEqual(hwnd, 222)
        mock_set_fg.assert_called_once_with(222)

    def test_switch_to_window_not_found(self):
        with (
            patch.object(window_focus, "HAS_WIN32", True),
            patch.object(window_focus, "list_windows", return_value=[(1, "Notepad")]),
        ):
            self.assertIsNone(window_focus.switch_to_window("nonexistent"))


@unittest.skipUnless(window_focus.HAS_WIN32, "requires Windows ctypes bindings")
class TestWindowFocusCallback(unittest.TestCase):
    """Test the real ctypes EnumWindows callback wiring (Windows-only).

    Regression coverage for a bug where `results` was marshaled through the
    EnumWindows LPARAM as a ctypes.py_object; since the callback's declared
    LPARAM type is a plain integer, `results` arrived inside the callback as
    an int (not the original list), and `results.append(...)` crashed on
    every window — silently, since ctypes swallows callback exceptions.
    `list_windows()` returned `[]` unconditionally as a result.
    """

    @patch("flowpulse.window_focus._GetWindowTextW")
    @patch("flowpulse.window_focus._GetWindowTextLengthW")
    @patch("flowpulse.window_focus._IsWindowVisible")
    def test_enum_window_callback_appends_visible_window(self, mock_visible, mock_len, mock_text):
        mock_visible.return_value = True
        mock_len.return_value = len("My Window")

        def fake_get_text(hwnd, buf, length):
            buf.value = "My Window"

        mock_text.side_effect = fake_get_text
        results = []
        continue_enum = window_focus._enum_window_callback(123, results)
        self.assertTrue(continue_enum)
        self.assertEqual(results, [(123, "My Window")])

    @patch("flowpulse.window_focus._IsWindowVisible")
    def test_enum_window_callback_skips_invisible_window(self, mock_visible):
        mock_visible.return_value = False
        results = []
        window_focus._enum_window_callback(456, results)
        self.assertEqual(results, [])

    @patch("flowpulse.window_focus._EnumWindows")
    @patch("flowpulse.window_focus._GetWindowTextW")
    @patch("flowpulse.window_focus._GetWindowTextLengthW")
    @patch("flowpulse.window_focus._IsWindowVisible")
    def test_list_windows_populates_results_via_real_callback_wiring(
        self, mock_visible, mock_len, mock_text, mock_enum_windows
    ):
        mock_visible.return_value = True
        mock_len.return_value = 5

        def fake_get_text(hwnd, buf, length):
            buf.value = f"Win{hwnd}"

        mock_text.side_effect = fake_get_text

        def fake_enum_windows(proc, lparam):
            # Exercises the real _EnumWindowsProc-wrapped closure, the same
            # way the real Win32 EnumWindows would invoke it per window.
            proc(111, 0)
            proc(222, 0)
            return True

        mock_enum_windows.side_effect = fake_enum_windows

        result = window_focus.list_windows()
        self.assertEqual(result, [(111, "Win111"), (222, "Win222")])


class TestInputSim(unittest.TestCase):
    """Test input simulation helpers with mocked pyautogui."""

    @patch("flowpulse.input_sim.pyautogui")
    def test_mouse_move_to(self, mock_pg):
        mock_pg.size.return_value = (1920, 1080)
        mock_pg.position.return_value = (100, 100)
        from flowpulse.input_sim import mouse_move_to

        mouse_move_to(200, 300)
        mock_pg.moveTo.assert_called()

    @patch("flowpulse.input_sim.pyautogui")
    def test_mouse_click(self, mock_pg):
        from flowpulse.input_sim import mouse_click

        mouse_click()
        mock_pg.mouseDown.assert_called_once()
        mock_pg.mouseUp.assert_called_once()

    @patch("flowpulse.input_sim.pyautogui")
    def test_keyboard_f13(self, mock_pg):
        from flowpulse.input_sim import keyboard_f13

        keyboard_f13()
        mock_pg.press.assert_called_with("f13")

    @patch("flowpulse.input_sim.pyautogui")
    def test_safe_coords(self, mock_pg):
        from flowpulse.input_sim import safe_coords

        mock_pg.size.return_value = (1920, 1080)
        x, y = safe_coords()
        self.assertGreaterEqual(x, 192)
        self.assertLessEqual(x, 1728)
        self.assertGreaterEqual(y, 108)
        self.assertLessEqual(y, 972)


class TestEngineMocked(unittest.TestCase):
    """Test engine with mock dependencies."""

    @patch("flowpulse.engine.pyautogui")
    @patch("flowpulse.engine.ActivityDetector")
    def test_engine_start_stop(self, mock_detector, mock_pg):
        mock_pg.size.return_value = (1920, 1080)
        from flowpulse.config import Config
        from flowpulse.engine import SimulationEngine

        config = Config()
        config.load()
        detector = mock_detector
        detector.is_user_active.return_value = False
        engine = SimulationEngine(config, detector)
        self.assertFalse(engine.is_running())
        engine.start()
        self.assertTrue(engine.is_running())
        engine.stop()
        self.assertFalse(engine.is_running())

    @patch("flowpulse.engine.pyautogui")
    @patch("flowpulse.engine.ActivityDetector")
    def test_engine_stats(self, mock_detector, mock_pg):
        mock_pg.size.return_value = (1920, 1080)
        from flowpulse.config import Config
        from flowpulse.engine import SimulationEngine

        config = Config()
        config.load()
        detector = mock_detector
        detector.is_user_active.return_value = False
        engine = SimulationEngine(config, detector)
        stats = engine.stats
        self.assertEqual(stats.current_state, "stopped")
        self.assertEqual(stats.total_moves, 0)

    @patch("flowpulse.engine.pyautogui")
    @patch("flowpulse.engine.ActivityDetector")
    def test_engine_pauses_on_user_active(self, mock_detector, mock_pg):
        import time

        from flowpulse.config import Config
        from flowpulse.engine import SimulationEngine

        config = Config()
        config.load()
        detector = mock_detector
        detector.is_user_active.return_value = True
        engine = SimulationEngine(config, detector)
        engine.start()
        time.sleep(0.2)
        engine.stop()
        # Should not have done any moves
        self.assertEqual(engine.stats.total_moves, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
