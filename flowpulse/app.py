"""FlowPulse application entry point — system tray app."""

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
# Optional imports (graceful degradation)
# ---------------------------------------------------------------------------

try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False

    class pystray:  # type: ignore[no-redef]
        class Icon:
            def __init__(self, *a, **kw): pass
            def run(self): pass
            def stop(self): pass

    class Image:  # type: ignore[no-redef]
        @staticmethod
        def new(*a, **kw):
            class _Img:
                def save(self, *a, **kw): pass
            return _Img()

    class ImageDraw:  # type: ignore[no-redef]
        @staticmethod
        def Draw(*a, **kw):
            class _Drw:
                def rectangle(self, *a, **kw): pass
                def text(self, *a, **kw): pass
            return _Drw()


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def _get_log_dir() -> str:
    if platform.system() == "Windows":
        base = os.environ.get("APPDATA", os.path.expanduser("~\\AppData\\Roaming"))
    else:
        base = os.path.expanduser("~")
    return os.path.join(base, "FlowPulse", "logs")


def setup_logging(config: Config) -> None:
    """Configure rotating-file + stderr logging."""
    log_dir = _get_log_dir()
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "flowpulse.log")

    level = getattr(logging, config.get("log_level", "INFO").upper(), logging.INFO)
    max_bytes = int(config.get("log_max_bytes", 1_048_576))
    backup_count = int(config.get("log_backup_count", 5))

    root = logging.getLogger()
    root.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler
    fh = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8",
    )
    fh.setLevel(level)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # Console handler (stderr)
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(level)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    logger.info("FlowPulse v%s — logging to %s", __version__, log_path)


# ---------------------------------------------------------------------------
# Tray icon generation
# ---------------------------------------------------------------------------

def _create_tray_image() -> "Image":
    """Generate a simple 64x64 tray icon using PIL."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw a small "pulse" shape
    cx, cy = size // 2, size // 2
    r1, r2 = 10, 22
    draw.ellipse(
        [cx - r2, cy - r2, cx + r2, cy + r2],
        fill=(0, 180, 255, 220),
    )
    draw.ellipse(
        [cx - r1, cy - r1, cx + r1, cy + r1],
        fill=(0, 120, 255, 255),
    )
    # Center dot
    draw.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=(255, 255, 255, 255))
    return img


# ---------------------------------------------------------------------------
# Application class
# ---------------------------------------------------------------------------

class FlowPulseApp:
    """Main application orchestrating the tray icon, config, and engine."""

    def __init__(self) -> None:
        self.config = Config()
        self.config.load()
        self.detector = ActivityDetector(
            timeout=float(self.config.get("idle_timeout_sec", 30))
        )
        self.engine = SimulationEngine(self.config, self.detector)
        self._tray: Optional[pystray.Icon] = None
        self._lock = threading.Lock()
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start the application (tray icon + detector)."""
        setup_logging(self.config)

        if not HAS_TRAY:
            logger.error("pystray not installed — cannot create system tray icon")
            sys.exit(1)

        self.detector.start()

        icon_img = _create_tray_image()
        menu = pystray.Menu(
            pystray.MenuItem("Start", self._on_start, default=True),
            pystray.MenuItem("Stop", self._on_stop),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Config", self._on_config),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", self._on_exit),
        )

        self._tray = pystray.Icon(
            "FlowPulse",
            icon_img,
            menu=menu,
            title=f"FlowPulse v{__version__}",
        )

        # Catch signals for clean shutdown
        signal.signal(signal.SIGINT, lambda s, f: self._tray.stop() if self._tray else None)
        signal.signal(signal.SIGTERM, lambda s, f: self._tray.stop() if self._tray else None)

        logger.info("FlowPulse ready — tray icon running")
        self._tray.run()  # blocks until stop

        # Cleanup after tray exits
        self._shutdown()

    def _shutdown(self) -> None:
        """Clean up engine and detector on exit."""
        logger.info("Shutting down FlowPulse")
        self.engine.stop()
        self.detector.stop()

    # ------------------------------------------------------------------
    # Menu callbacks
    # ------------------------------------------------------------------

    def _on_start(self, *args) -> None:
        """Start the simulation engine."""
        with self._lock:
            if self._running:
                logger.info("Already running — ignoring Start")
                return
            self.engine.start()
            self._running = True
            self._update_tray_title("FlowPulse — Running")
            logger.info("Simulation started via tray menu")

    def _on_stop(self, *args) -> None:
        """Stop the simulation engine."""
        with self._lock:
            if not self._running:
                logger.info("Not running — ignoring Stop")
                return
            self.engine.stop()
            self._running = False
            self._update_tray_title(f"FlowPulse v{__version__}")
            logger.info("Simulation stopped via tray menu")

    def _on_config(self, *args) -> None:
        """Open config file in default editor or print path."""
        cfg_path = self.config.path
        logger.info("Config file: %s", cfg_path)
        # On Windows: try notepad; on Linux/macOS: just log the path
        if platform.system() == "Windows" and os.path.isfile(cfg_path):
            os.startfile(cfg_path)
        else:
            logger.info("Open %s to edit configuration", cfg_path)

    def _on_exit(self, *args) -> None:
        """Exit the application."""
        logger.info("Exit requested via tray menu")
        if self._tray is not None:
            self._tray.stop()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_tray_title(self, title: str) -> None:
        if self._tray is not None:
            self._tray.title = title


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    app = FlowPulseApp()
    app.run()


if __name__ == "__main__":
    main()
