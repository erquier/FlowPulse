"""Window focus rotation (Windows-only via EnumWindows)."""

import logging
import random

logger = logging.getLogger(__name__)

# Try to import Windows-specific APIs; gracefully degrade on other platforms.
try:
    import ctypes
    import ctypes.wintypes

    _user32 = ctypes.windll.user32
    _EnumWindows = _user32.EnumWindows
    _GetWindowTextW = _user32.GetWindowTextW
    _GetWindowTextLengthW = _user32.GetWindowTextLengthW
    _IsWindowVisible = _user32.IsWindowVisible
    _SetForegroundWindow = _user32.SetForegroundWindow
    _EnumWindowsProc = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
    )

    HAS_WIN32 = True
except (ImportError, AttributeError, OSError):
    HAS_WIN32 = False


def _enum_window_callback(hwnd: int, results: list[tuple[int, str]]) -> bool:
    """Callback for EnumWindows: collect visible windows with titles."""
    if _IsWindowVisible(hwnd):
        length = _GetWindowTextLengthW(hwnd) + 1
        buf = ctypes.create_unicode_buffer(length)
        _GetWindowTextW(hwnd, buf, length)
        title = buf.value.strip()
        if title:
            results.append((hwnd, title))
    return True  # continue enumeration


def list_windows() -> list[tuple[int, str]]:
    """Return a list of (hwnd, title) for all visible top-level windows."""
    results: list[tuple[int, str]] = []
    if not HAS_WIN32:
        return results

    # Capture `results` via closure rather than marshaling it through the
    # EnumWindows LPARAM: LPARAM is a plain integer, so a ctypes.py_object
    # passed there arrives in the callback as an int, not the original list.
    def _callback(hwnd: int, _lparam: int) -> bool:
        return _enum_window_callback(hwnd, results)

    _EnumWindows(_EnumWindowsProc(_callback), 0)
    return results


def rotate() -> int | None:
    """Switch focus to a random visible window.

    Returns the HWND of the newly focused window, or None if:
      - Not on Windows
      - Fewer than 2 visible windows are available
    """
    if not HAS_WIN32:
        logger.debug("rotate(): not on Windows, skipping")
        return None

    windows = list_windows()
    if len(windows) < 2:
        logger.debug("rotate(): fewer than 2 windows available (%d)", len(windows))
        return None

    # Pick a random window
    hwnd, title = random.choice(windows)
    logger.info("Rotating focus to window: %s (hwnd=%d)", title, hwnd)
    _SetForegroundWindow(hwnd)
    return hwnd


def switch_to_window(title_substring: str) -> int | None:
    """Bring the first visible window whose title contains *title_substring* to the foreground.

    Returns the HWND on success, or None if no matching window is found.
    """
    if not HAS_WIN32:
        return None

    for hwnd, title in list_windows():
        if title_substring.lower() in title.lower():
            _SetForegroundWindow(hwnd)
            logger.info("Switched to window: %s (hwnd=%d)", title, hwnd)
            return hwnd

    logger.debug("No visible window found containing %r", title_substring)
    return None
