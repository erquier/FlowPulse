# DEPRECATED — XOR obfuscation, process monitoring detection, and safe naming. Not integrated into the runtime. Kept for future use.
"""Stealth helpers: obfuscation, process detection, safe naming, install paths."""

import os
import platform
import subprocess
from collections.abc import Iterator

# ---------------------------------------------------------------------------
# XOR obfuscation with rotating key
# ---------------------------------------------------------------------------


def _xor_rotate(data: bytes, key: bytes) -> bytes:
    """XOR *data* with *key*, rotating the key cyclically."""
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def obfuscate(text: str, key: bytes = b"FlowPulse2024!@#$") -> str:
    """Return a hex-encoded, XOR-obfuscated version of *text*."""
    if not text:
        return ""
    raw = text.encode("utf-8")
    xored = _xor_rotate(raw, key)
    return xored.hex()


def deobfuscate(hex_str: str, key: bytes = b"FlowPulse2024!@#$") -> str:
    """Restore the original string from a hex-encoded obfuscated value."""
    if not hex_str:
        return ""
    raw = bytes.fromhex(hex_str)
    xored = _xor_rotate(raw, key)
    return xored.decode("utf-8")


# ---------------------------------------------------------------------------
# Process / monitoring detection (Windows-only meaningful)
# ---------------------------------------------------------------------------

MONITORING_PROCESS_NAMES = frozenset(
    {
        "TRAgent.exe",
        "Teramind.exe",
        "TRAgent",
        "Teramind",
    }
)


def _running_processes() -> Iterator[str]:
    """Yield process names currently running on the system."""
    if platform.system() == "Windows":
        try:
            output = subprocess.check_output(
                ["tasklist", "/FO", "CSV", "/NH"],
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=10,
                text=True,
            )
            for line in output.strip().splitlines():
                parts = line.split(",")
                if len(parts) >= 1:
                    yield parts[0].strip('"').strip()
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
    else:
        # Linux/macOS fallback: check common processes via pgrep
        try:
            output = subprocess.check_output(
                ["pgrep", "-l", "-f", "Teramind|TRAgent"],
                timeout=10,
                text=True,
            )
            for line in output.strip().splitlines():
                parts = line.split(None, 1)
                if len(parts) >= 2:
                    yield parts[1]
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
            pass


def is_monitoring_running() -> bool:
    """Return True if a known monitoring agent process is detected."""
    for name in _running_processes():
        if name in MONITORING_PROCESS_NAMES:
            return True
    return False


# ---------------------------------------------------------------------------
# Safe / generic Windows executable names
# ---------------------------------------------------------------------------

_SAFE_NAMES: list[str] = [
    "WindowsAssistant",
    "SystemHelper",
    "BackgroundHost",
    "ServiceManager",
    "DesktopEnhancer",
    "UserInterfaceService",
    "RuntimeBroker",
    "ApplicationFrameHost",
]


def safe_exit_name() -> str:
    """Return a generic, non-suspicious Windows-style process name."""
    import random

    return random.choice(_SAFE_NAMES)


# ---------------------------------------------------------------------------
# Install path
# ---------------------------------------------------------------------------


def get_install_path() -> str:
    """Return the FlowPulse install directory (under %APPDATA% on Windows)."""
    if platform.system() == "Windows":
        base = os.environ.get("APPDATA", os.path.expanduser("~\\AppData\\Roaming"))
    else:
        base = os.path.expanduser("~")
    return os.path.join(base, "FlowPulse")
