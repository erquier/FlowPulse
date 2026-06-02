#!/usr/bin/env python3
"""Quick smoke test for FlowPulse logic components."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flowpulse.config import Config
from flowpulse.scheduler import ActivityScheduler
from flowpulse.movement import generate_path
from flowpulse import __version__

print(f"[SMOKE] FlowPulse v{__version__}")

# Scheduler
import random
random.seed(42)
s = ActivityScheduler()
b = s.next_burst_duration()
p = s.next_pause_duration()
assert 5 <= b <= 15, f"burst {b} out of range"
assert 2 <= p <= 5, f"pause {p} out of range"
print(f"[SMOKE] scheduler OK: burst={b:.1f}min pause={p:.1f}min")

# Movement
path = generate_path(100, 100, 500, 300)
assert len(path) > 5, f"path too short: {len(path)}"
print(f"[SMOKE] movement OK: {len(path)} path points, ends at ({path[-1][0]:.0f},{path[-1][1]:.0f})")

# Config
cfg = Config()
cfg.load()
assert cfg.get("burst_min_moves", 0) == 8
cfg.set("_smoke_test", 42)
assert cfg.get("_smoke_test") == 42
print(f"[SMOKE] config OK: loaded={cfg.path}")

print("[SMOKE] All components verified ✓")
sys.exit(0)
