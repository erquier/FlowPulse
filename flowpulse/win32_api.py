"""Shared low-level Win32 bindings (raw ctypes) for detector.py and window_focus.py.

Both modules used to independently declare their own HAS_WIN32-style
availability flag (set via try/except at import time so the module stays
importable on non-Windows platforms) and their own lazy ctypes bindings
to a handful of user32/kernel32 functions. Centralized here so there's
one canonical guard and one place that knows how to degrade gracefully.

app.py's Win32 usage (pywin32's win32api/win32con/win32gui, for the tray
icon and message loop) is intentionally NOT included here: it's a
different, already well-abstracted library used for a single cohesive
purpose with no duplication elsewhere, so folding it into this
raw-ctypes module would mix two different API layers for no real
benefit.
"""

import ctypes
import ctypes.wintypes

HAS_WIN32 = False
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

    _EnumWindows = _user32.EnumWindows
    _GetWindowTextW = _user32.GetWindowTextW
    _GetWindowTextLengthW = _user32.GetWindowTextLengthW
    _IsWindowVisible = _user32.IsWindowVisible
    _SetForegroundWindow = _user32.SetForegroundWindow
    _EnumWindowsProc = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
    )

    HAS_WIN32 = True
except (AttributeError, OSError):
    # Non-Windows system -- callers fall back to platform-independent
    # behavior (e.g. ActivityDetector relies on pynput listeners only;
    # window_focus.rotate()/switch_to_window() become no-ops).
    pass


# ---------------------------------------------------------------------------
# GetLastInputInfo (used by detector.py)
# ---------------------------------------------------------------------------


def milliseconds_since_last_input() -> int | None:
    """Return ms since the last system-wide input event, or None if
    unavailable (non-Windows, or the underlying API call failed)."""
    if not HAS_WIN32:
        return None
    try:
        lii = _LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(_LASTINPUTINFO)
        if not _GetLastInputInfo(ctypes.byref(lii)):
            return None
        tick_now = _GetTickCount()
        return (tick_now - lii.dwTime) & 0xFFFFFFFF
    except Exception:
        return None


# ---------------------------------------------------------------------------
# EnumWindows / SetForegroundWindow (used by window_focus.py)
# ---------------------------------------------------------------------------


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


def list_visible_windows() -> list[tuple[int, str]]:
    """Return a list of (hwnd, title) for all visible top-level windows."""
    results: list[tuple[int, str]] = []
    if not HAS_WIN32:
        return results

    # Capture `results` via closure rather than marshaling it through the
    # EnumWindows LPARAM: LPARAM is a plain integer, so a ctypes.py_object
    # passed there would arrive in the callback as an int, not the list.
    def _callback(hwnd: int, _lparam: int) -> bool:
        return _enum_window_callback(hwnd, results)

    _EnumWindows(_EnumWindowsProc(_callback), 0)
    return results


def set_foreground_window(hwnd: int) -> None:
    """Bring the given window to the foreground."""
    _SetForegroundWindow(hwnd)
