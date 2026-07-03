#!/usr/bin/env python3
"""Quick smoke test for FlowPulse logic components."""

import os
import random
import sys

# Windows consoles often default to a legacy codepage (e.g. cp1252) that
# can't encode the checkmark below; force UTF-8 so this runs the same in
# a native Windows terminal as it does under CI's UTF-8 locale.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flowpulse import __version__
from flowpulse.config import Config
from flowpulse.engine import SimulationEngine
from flowpulse.movement import generate_path

print(f"[SMOKE] FlowPulse v{__version__}")

# Activity scheduling (SimulationEngine's ported burst/pause helpers)
random.seed(42)
_scheduling_cfg = Config()
_scheduling_cfg.load()
_engine = SimulationEngine(_scheduling_cfg, detector=None)
factor = _engine._time_of_day_factor()
interval = _engine._next_activity_interval(factor=factor)
pause, is_long = _engine._next_pause_seconds()
assert 0.0 <= factor <= 1.0, f"time-of-day factor {factor} out of range"
assert interval > 0, f"activity interval {interval} not positive"
assert pause > 0, f"pause {pause} not positive"
print(f"[SMOKE] scheduling OK: factor={factor:.2f} interval={interval:.2f}s pause={pause:.1f}s")

# Movement
path = generate_path(100, 100, 500, 300)
assert len(path) > 5, f"path too short: {len(path)}"
print(
    f"[SMOKE] movement OK: {len(path)} path points, ends at ({path[-1][0]:.0f},{path[-1][1]:.0f})"
)

# Config
cfg = Config()
cfg.load()
assert cfg.get("burst_min_moves", 0) == 8
cfg.set("_smoke_test", 42)
assert cfg.get("_smoke_test") == 42
print(f"[SMOKE] config OK: loaded={cfg.path}")

print("[SMOKE] All components verified ✓")
sys.exit(0)
