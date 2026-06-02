"""FlowPulse — System tray + tkinter settings UI.
Uses win32gui directly for tray icon (more reliable with Nuitka)
and tkinter for the configuration dialog.
"""
import logging
import logging.handlers
import os
import platform
import signal
import sys
import threading
from typing import Optional

from flowpulse import __version__
from flowpulse.config import Config
from flowpulse.detector import ActivityDetector
from flowpulse.engine import SimulationEngine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tray icon via win32gui (reliable with Nuitka)
# ---------------------------------------------------------------------------

import win32gui
import win32con
import win32api

WM_TASKBAR_CREATED = win32api.RegisterWindowMessage("TaskbarCreated")
WM_USER_TRAY = win32con.WM_USER + 1
WM_USER_EXIT = win32con.WM_USER + 2
WM_USER_CONFIG = win32con.WM_USER + 3
WM_USER_START = win32con.WM_USER + 4
WM_USER_STOP = win32con.WM_USER + 5
WM_USER_SHOW_LOG = win32con.WM_USER + 6
GUID_TRAY = "{B8F3C0A0-9E3F-4A1D-9F2C-7B1E4A2D8C0F}"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _get_log_dir() -> str:
    if platform.system() == "Windows":
        base = os.environ.get("APPDATA", os.path.expanduser("~\\AppData\\Roaming"))
    else:
        base = os.path.expanduser("~")
    return os.path.join(base, "FlowPulse", "logs")


def setup_logging(config: Config) -> None:
    log_dir = _get_log_dir()
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "flowpulse.log")
    level = getattr(logging, config.get("log_level", "INFO").upper(), logging.INFO)
    max_bytes = int(config.get("log_max_bytes", 1_048_576))
    backup_count = int(config.get("log_backup_count", 5))
    root = logging.getLogger()
    root.setLevel(level)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    fh = logging.handlers.RotatingFileHandler(log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(fmt)
    root.addHandler(fh)
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(level)
    ch.setFormatter(fmt)
    root.addHandler(ch)
    logger.info("FlowPulse v%s — logging to %s", __version__, log_path)

# ---------------------------------------------------------------------------
# Settings dialog (tkinter)
# ---------------------------------------------------------------------------

def _show_settings_dialog(config: Config) -> None:
    """Open a tkinter settings dialog and apply changes."""
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError:
        logger.warning("tkinter not available — cannot show settings dialog")
        return

    root = tk.Tk()
    root.title("FlowPulse Settings")
    root.geometry("480x400")
    root.resizable(False, False)

    # Try to set icon if available
    ico = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icon.ico")
    if os.path.isfile(ico):
        try:
            root.iconbitmap(ico)
        except Exception:
            pass

    frame = ttk.Frame(root, padding="12")
    frame.pack(fill=tk.BOTH, expand=True)

    row = 0
    fields = {}

    def add_field(label, key, from_=None, to_=None, fmt="int"):
        nonlocal row
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky=tk.W, pady=3)
        var = tk.StringVar(value=str(config.get(key, "")))
        if from_ is not None:
            scale = ttk.Scale(frame, from_=from_, to=to_, orient=tk.HORIZONTAL, length=250)
            scale.set(float(config.get(key, (from_ + to_) / 2)))
            scale.grid(row=row, column=1, sticky=tk.EW, padx=6, pady=3)
            lbl = ttk.Label(frame, text=var.get())
            lbl.grid(row=row, column=2, padx=3)
            fields[key] = (var, scale, lbl, fmt)
        else:
            entry = ttk.Entry(frame, textvariable=var, width=30)
            entry.grid(row=row, column=1, sticky=tk.EW, padx=6, pady=3)
            fields[key] = var
        row += 1

    def on_scale_change(key):
        var, scale, lbl, fmt = fields[key]
        val = int(scale.get()) if fmt == "int" else round(scale.get(), 1)
        var.set(str(val))
        lbl.config(text=str(val))

    add_field("Moves per burst (min)", "burst_min_moves", 3, 30)
    add_field("Moves per burst (max)", "burst_max_moves", 5, 60)
    add_field("Pause corta (s)", "read_pause_min_sec", 1, 30)
    add_field("Pause corta (max s)", "read_pause_max_sec", 5, 60)
    add_field("Pause larga (s)", "long_pause_min_sec", 10, 300)
    add_field("Pause larga (max s)", "long_pause_max_sec", 30, 600)
    add_field("Velocidad mouse min", "mouse_speed_min", 0.05, 1.0, fmt="float")
    add_field("Velocidad mouse max", "mouse_speed_max", 0.1, 2.0, fmt="float")

    row += 1
    bool_fields = {}
    for label, key in [("Simular teclado (F13)", "keyboard_enabled"),
                       ("Rotar ventanas activas", "focus_enabled"),
                       ("Auto-start al abrir", "auto_start")]:
        var = tk.BooleanVar(value=config.get(key, False))
        cb = ttk.Checkbutton(frame, text=label, variable=var)
        cb.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=2)
        bool_fields[key] = var
        row += 1

    # Add listeners for scale updates
    for key in ["burst_min_moves", "burst_max_moves", "read_pause_min_sec",
                "read_pause_max_sec", "long_pause_min_sec", "long_pause_max_sec",
                "mouse_speed_min", "mouse_speed_max"]:
        if key in fields:
            var, scale, lbl, fmt = fields[key]
            scale.config(command=lambda v, k=key: on_scale_change(k))

    def on_save():
        for key in bool_fields:
            config.set(key, bool_fields[key].get())
        for key in fields:
            var, scale, lbl, fmt = fields[key]
            config.set(key, int(var.get()) if fmt == "int" else float(var.get()))
        config.save()
        logger.info("Settings saved via dialog")
        root.destroy()

    def on_cancel():
        root.destroy()

    btn_frame = ttk.Frame(frame)
    btn_frame.grid(row=row, column=0, columnspan=3, pady=12)
    ttk.Button(btn_frame, text="Save", command=on_save).pack(side=tk.LEFT, padx=4)
    ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side=tk.LEFT, padx=4)
    ttk.Button(btn_frame, text="Open Log", command=lambda: _open_log()).pack(side=tk.LEFT, padx=4)

    frame.columnconfigure(1, weight=1)
    root.mainloop()


def _open_log():
    log_path = os.path.join(_get_log_dir(), "flowpulse.log")
    if os.path.isfile(log_path):
        os.startfile(log_path)

# ---------------------------------------------------------------------------
# FlowPulseApp
# ---------------------------------------------------------------------------

class FlowPulseApp:
    def __init__(self) -> None:
        self.config = Config()
        self.config.load()
        self.detector = ActivityDetector(timeout=float(self.config.get("idle_timeout_sec", 30)))
        self.engine = SimulationEngine(self.config, self.detector)
        self._lock = threading.Lock()
        self._running = False
        self._hwnd: Optional[int] = None
        self._icon_id = 1001
        self._tray_visible = False

    def run(self) -> None:
        setup_logging(self.config)
        self.detector.start()
        logger.info("FlowPulse starting...")

        # Create hidden message window for tray icon
        wc = win32gui.WNDCLASS()
        wc.hInstance = win32api.GetModuleHandle(None)
        wc.lpszClassName = "FlowPulseTray"
        wc.style = win32con.CS_HREDRAW | win32con.CS_VREDRAW
        wc.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
        wc.hbrBackground = win32con.COLOR_WINDOW
        wc.lpfnWndProc = self._window_proc
        class_atom = win32gui.RegisterClass(wc)
        self._hwnd = win32gui.CreateWindow(
            class_atom, "FlowPulse",
            win32con.WS_OVERLAPPEDWINDOW,
            0, 0, 0, 0, 0, 0,
            wc.hInstance, None
        )
        win32gui.UpdateWindow(self._hwnd)
        self._show_tray_icon()

        # Auto-start if configured
        if self.config.get("auto_start", False):
            self._on_start()

        logger.info("FlowPulse ready — message loop running")

        # Windows message loop
        try:
            win32gui.PumpMessages()
        except KeyboardInterrupt:
            pass
        finally:
            self._shutdown()

    def _window_proc(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        if msg == WM_TASKBAR_CREATED:
            self._show_tray_icon()
            return 0
        if msg == WM_USER_EXIT:
            self._hide_tray_icon()
            win32gui.DestroyWindow(hwnd)
            return 0
        if msg == WM_USER_CONFIG:
            self._on_config()
            return 0
        if msg == WM_USER_START:
            self._on_start()
            return 0
        if msg == WM_USER_STOP:
            self._on_stop()
            return 0
        if msg == WM_USER_SHOW_LOG:
            _open_log()
            return 0
        if msg == WM_USER_TRAY:
            if lparam == win32con.WM_LBUTTONUP:
                # Left click: show config
                win32gui.PostMessage(hwnd, WM_USER_CONFIG, 0, 0)
            elif lparam == win32con.WM_RBUTTONUP:
                # Right click: show context menu
                self._show_context_menu()
            return 0
        if msg == win32con.WM_DESTROY:
            win32gui.PostQuitMessage(0)
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _show_tray_icon(self) -> None:
        if self._tray_visible:
            return

        # Load icon from assets or use default
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icon.ico")
        if os.path.isfile(icon_path):
            hicon = win32gui.LoadImage(
                0, icon_path, win32con.IMAGE_ICON,
                16, 16, win32con.LR_LOADFROMFILE
            )
        else:
            hicon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)

        flags = win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP | win32gui.NIF_GUID
        nid = (
            self._hwnd, self._icon_id,
            flags, WM_USER_TRAY,
            hicon, "FlowPulse — Stopped",
            GUID_TRAY
        )
        try:
            win32gui.Shell_NotifyIcon(win32con.NIM_ADD, nid)
            self._tray_visible = True
            logger.info("Tray icon added")
        except Exception as e:
            logger.error("Failed to create tray icon: %s", e)

    def _hide_tray_icon(self) -> None:
        if self._tray_visible:
            try:
                nid = (self._hwnd, self._icon_id)
                win32gui.Shell_NotifyIcon(win32con.NIM_DELETE, nid)
                self._tray_visible = False
                logger.info("Tray icon removed")
            except Exception as e:
                logger.error("Failed to remove tray icon: %s", e)

    def _update_tray_tip(self, text: str) -> None:
        if self._tray_visible:
            nid = (
                self._hwnd, self._icon_id,
                win32gui.NIF_TIP, 0, 0, text, ""
            )
            try:
                win32gui.Shell_NotifyIcon(win32con.NIM_MODIFY, nid)
            except Exception:
                pass

    def _show_context_menu(self) -> None:
        menu = win32gui.CreatePopupMenu()
        if self._running:
            win32gui.AppendMenu(menu, win32con.MF_STRING, WM_USER_STOP, "Stop")
        else:
            win32gui.AppendMenu(menu, win32con.MF_STRING, WM_USER_START, "Start")
        win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, "")
        win32gui.AppendMenu(menu, win32con.MF_STRING, WM_USER_CONFIG, "Settings")
        win32gui.AppendMenu(menu, win32con.MF_STRING, WM_USER_SHOW_LOG, "View Log")
        win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, "")
        win32gui.AppendMenu(menu, win32con.MF_STRING, WM_USER_EXIT, "Exit")

        # Get cursor position for menu
        pos = win32gui.GetCursorPos()
        win32gui.SetForegroundWindow(self._hwnd)
        win32gui.TrackPopupMenu(menu, win32con.TPM_LEFTALIGN, pos[0], pos[1], 0, self._hwnd, None)
        win32gui.PostMessage(self._hwnd, win32con.WM_NULL, 0, 0)

    def _on_start(self) -> None:
        with self._lock:
            if self._running:
                logger.info("Already running")
                return
            self.engine.start()
            self._running = True
            self._update_tray_tip("FlowPulse — Running")
            logger.info("Engine started")

    def _on_stop(self) -> None:
        with self._lock:
            if not self._running:
                logger.info("Not running")
                return
            self.engine.stop()
            self._running = False
            self._update_tray_tip("FlowPulse — Stopped")
            logger.info("Engine stopped")

    def _on_config(self) -> None:
        logger.info("Opening settings dialog")
        threading.Thread(target=_show_settings_dialog, args=(self.config,), daemon=True).start()

    def _shutdown(self) -> None:
        self._hide_tray_icon()
        self.engine.stop()
        self.detector.stop()
        logger.info("FlowPulse shut down")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    app = FlowPulseApp()
    app.run()


if __name__ == "__main__":
    main()
