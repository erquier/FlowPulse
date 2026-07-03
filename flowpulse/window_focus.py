"""Window focus rotation (Windows-only via EnumWindows)."""

import logging
import random

from flowpulse import win32_api

logger = logging.getLogger(__name__)

HAS_WIN32 = win32_api.HAS_WIN32


def list_windows() -> list[tuple[int, str]]:
    """Return a list of (hwnd, title) for all visible top-level windows."""
    if not HAS_WIN32:
        return []
    return win32_api.list_visible_windows()


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
    win32_api.set_foreground_window(hwnd)
    return hwnd


def switch_to_window(title_substring: str) -> int | None:
    """Bring the first visible window whose title contains *title_substring* to the foreground.

    Returns the HWND on success, or None if no matching window is found.
    """
    if not HAS_WIN32:
        return None

    for hwnd, title in list_windows():
        if title_substring.lower() in title.lower():
            win32_api.set_foreground_window(hwnd)
            logger.info("Switched to window: %s (hwnd=%d)", title, hwnd)
            return hwnd

    logger.debug("No visible window found containing %r", title_substring)
    return None
