"""
movement.py — Bezier curve mouse movement with realistic human characteristics.

Provides bezier_move() for raw curve generation and generate_path() for
point-to-point movement with overshoot, tremor, and jitter.
"""

import math
import random


def _smoothstep(t: float) -> float:
    """Hermite smoothstep: 3t² - 2t³."""
    return t * t * (3.0 - 2.0 * t)


def _ease_in_out(t: float) -> float:
    """Ease-in-out smoothstyle: accelerated start, decelerated end."""
    if t < 0.5:
        return 2.0 * t * t
    return 1.0 - (-2.0 * t + 2.0) ** 2 * 0.5


def _perpendicular_offset(ax: float, ay: float, bx: float, by: float) -> tuple[float, float]:
    """
    Compute a control point offset perpendicular to the line A→B,
    scaled by 40% of the distance. Direction is randomised.
    """
    dx = bx - ax
    dy = by - ay
    dist = math.hypot(dx, dy)
    if dist < 1e-6:
        return 0.0, 0.0
    # unit perpendicular
    px = -dy / dist
    py = dx / dist
    # randomise left/right
    if random.random() < 0.5:
        px = -px
        py = -py
    offset = dist * 0.40
    return px * offset, py * offset


def bezier_move(
    ax: float,
    ay: float,
    bx: float,
    by: float,
    duration_ms: int | None = 500,
    samples: int | None = None,
) -> list[tuple[float, float, float]]:
    """
    Generate a cubic Bezier path from (ax,ay) to (bx,by).

    Control points:
      C1 = start + perpendicular offset (biased toward direction)
      C2 = end   + perpendicular offset (biased toward direction)

    Returns list of (x, y, time_ratio) where time_ratio ∈ [0, 1].
    Overshoot and tremor are NOT applied here — use generate_path().
    """
    dist = math.hypot(bx - ax, by - ay)

    # scale duration if none given -- must run before the samples default
    # below, which divides by duration_ms.
    if duration_ms is None:
        if dist < 100:
            duration_ms = random.randint(200, 400)
        elif dist > 500:
            duration_ms = random.randint(500, 1000)
        else:
            duration_ms = int(200 + (dist - 50) * 0.8)

    if samples is None:
        samples = max(10, int(duration_ms / 10))

    p_ox, p_oy = _perpendicular_offset(ax, ay, bx, by)

    c1x = ax + p_ox + (bx - ax) * 0.3
    c1y = ay + p_oy + (by - ay) * 0.3
    c2x = bx + p_ox - (bx - ax) * 0.3
    c2y = by + p_oy - (by - ay) * 0.3

    points = []
    for i in range(samples + 1):
        t = i / samples
        s = _ease_in_out(t)
        # cubic Bezier formula
        mt = 1.0 - s
        x = mt**3 * ax + 3 * mt**2 * s * c1x + 3 * mt * s**2 * c2x + s**3 * bx
        y = mt**3 * ay + 3 * mt**2 * s * c1y + 3 * mt * s**2 * c2y + s**3 * by
        points.append((x, y, t))

    return points


def _gaussian_noise(mu: float = 0.0, sigma: float = 1.0) -> float:
    """Box-Muller transform for Gaussian noise (no numpy)."""
    u1 = random.random()
    u2 = random.random()
    return mu + sigma * math.sqrt(-2.0 * math.log(u1 + 1e-12)) * math.cos(2.0 * math.pi * u2)


def generate_path(x1: float, y1: float, x2: float, y2: float) -> list[tuple[float, float, int]]:
    """
    Generate a full movement path from (x1,y1) to (x2,y2).

    The path includes:
      - Cubic Bezier curve with ease-in-out
      - Overshoot: passes 5-15 px beyond target
      - Tremor: micro-oscillations ±0.5px in final segment
      - Gaussian jitter on every point
      - Variable per-step delays

    Returns list of (x, y, delay_ms) ready for playback.
    """
    dist = math.hypot(x2 - x1, y2 - y1)

    # duration based on distance
    if dist < 100:
        duration_ms = random.randint(200, 400)
    elif dist > 500:
        duration_ms = random.randint(500, 1000)
    else:
        duration_ms = int(200 + (dist - 50) * 0.8)

    samples = max(8, min(40, int(duration_ms / 15)))

    # --- Overshoot target ---
    overshoot_px = random.uniform(5.0, 15.0)
    angle = math.atan2(y2 - y1, x2 - x1)
    overshoot_x = x2 + math.cos(angle) * overshoot_px
    overshoot_y = y2 + math.sin(angle) * overshoot_px

    # Generate Bezier to overshoot point
    raw = bezier_move(x1, y1, overshoot_x, overshoot_y, duration_ms, samples)

    path: list[tuple[float, float, int]] = []
    total = len(raw)

    for idx, (rx, ry, t) in enumerate(raw):
        # Gaussian jitter (±1.0px during travel, ±0.3px near start/end)
        jitter_sigma = 0.3 + 0.7 * (1.0 - abs(2.0 * t - 1.0))
        jx = _gaussian_noise(0.0, jitter_sigma * 0.5)
        jy = _gaussian_noise(0.0, jitter_sigma * 0.5)

        fx = rx + jx
        fy = ry + jy

        # --- Tremor (micro-oscillations) on last 20% of path ---
        if t > 0.8:
            tremor_phase = (t - 0.8) / 0.2 * math.pi * 3  # 1.5 cycles
            tremor_amp = 0.5 * (t - 0.8) / 0.2  # ramp up to 0.5px
            fx += math.sin(tremor_phase) * tremor_amp
            fy += math.cos(tremor_phase + 0.5) * tremor_amp

        # --- Overshoot correction on last 5 steps ---
        remaining = total - idx
        if remaining <= 5 and remaining > 0:
            correction = remaining / 5.0
            fx = fx + (x2 - fx) * (1.0 - correction)
            fy = fy + (y2 - fy) * (1.0 - correction)

        # compute delay for this step
        if idx == 0:
            delay = 0
        else:
            # base delay proportional to segment length
            seg_length = math.hypot(fx - path[-1][0], fy - path[-1][1])
            base_delay = max(5, int(seg_length * 2.5))
            # add gaussian noise
            noise = _gaussian_noise(0.0, 3.0)
            delay = max(2, int(base_delay + noise))

        path.append((fx, fy, delay))

    return path
