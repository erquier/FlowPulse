#!/usr/bin/env python3
"""FlowPulse — Build script for Nuitka compilation.

Generates a standalone, one-file Windows executable with:
- Legitimate metadata (Erqlabs, FlowPulse)
- Windows subsystem (no console)
- UPX compression (if available)
- Custom icon
"""

import os
import platform
import subprocess
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "dist")
ICON_PATH = os.path.join(PROJECT_ROOT, "assets", "icon.ico")

# --- Configuration ---
ENTRY_POINT = os.path.join(PROJECT_ROOT, "FlowPulse.py")
APP_NAME = "FlowPulse"
COMPANY_NAME = "Erqlabs"
PRODUCT_NAME = "FlowPulse"
FILE_VERSION = "1.1.0"
FILE_DESCRIPTION = "FlowPulse — Human-like input simulation"

NUITKA_FLAGS = [
    "--standalone",
    "--onefile",
    "--windows-disable-console",
    "--assume-yes-for-downloads",
    "--enable-plugin=tk-inter",
    f"--output-dir={OUTPUT_DIR}",
    f"--company-name={COMPANY_NAME}",
    f"--product-name={PRODUCT_NAME}",
    f"--file-version={FILE_VERSION}",
    f"--file-description={FILE_DESCRIPTION}",
    "--copyright=Erqlabs. All rights reserved.",
]

# Add icon if it exists
if os.path.isfile(ICON_PATH):
    NUITKA_FLAGS.append(f"--windows-icon-from-ico={ICON_PATH}")
else:
    print(f"[WARN] Icon not found at {ICON_PATH} — building without custom icon.")
    print("[WARN] Place a 256x256 .ico file at assets/icon.ico for production builds.")

# Try UPX if available
upx_paths = [
    os.path.join(PROJECT_ROOT, "tools", "upx", "upx.exe"),
    r"C:\tools\upx\upx.exe",
    r"C:\Program Files\UPX\upx.exe",
]
for upx in upx_paths:
    if os.path.isfile(upx):
        NUITKA_FLAGS.append(f"--upx={upx}")
        print(f"[INFO] Using UPX: {upx}")
        break
else:
    print("[INFO] UPX not found — skipping compression.")


def main():
    if not os.path.isfile(ENTRY_POINT):
        print(f"[ERROR] Entry point not found: {ENTRY_POINT}")
        sys.exit(1)

    if platform.system() != "Windows":
        print(
            "[WARN] This build script is designed for Windows. "
            "Cross-compilation is not supported. Run on a Windows host."
        )

    cmd = [sys.executable or "python", "-m", "nuitka", ENTRY_POINT] + NUITKA_FLAGS

    print(f"[BUILD] {APP_NAME} v{FILE_VERSION}")
    print(f"[BUILD] Entry point: {ENTRY_POINT}")
    print("[BUILD] Command:")
    print(f"  {' '.join(cmd)}")
    print("-" * 60)

    try:
        result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)
    except FileNotFoundError:
        print("[ERROR] Nuitka not found. Install it with: pip install nuitka")
        sys.exit(1)

    print(result.stdout)
    if result.returncode != 0:
        print("[ERROR] Build failed:")
        print(result.stderr)
        sys.exit(result.returncode)

    exe_path = os.path.join(OUTPUT_DIR, f"{APP_NAME}.exe")
    if os.path.isfile(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print(f"[OK] Build successful: {exe_path} ({size_mb:.2f} MB)")
    else:
        print("[WARN] Build completed but EXE not found at expected path.")
        print(f"      Expected: {exe_path}")
        # List output directory
        if os.path.isdir(OUTPUT_DIR):
            print(f"      Files in {OUTPUT_DIR}:")
            for f in os.listdir(OUTPUT_DIR):
                print(f"        - {f}")


if __name__ == "__main__":
    main()
