# DEPRECATED — this module is not used by the runtime engine. The SimulationEngine in engine.py has its own burst/pause loop. Kept for test compatibility (tests/test_all.py has 22 test methods for ActivityScheduler).
"""
scheduler.py — Realistic activity burst scheduler for FlowPulse.

Distributes mouse/keyboard actions in bursts separated by pauses,
with time-of-day activity factors and long-pause recovery intervals.
"""

import math
import random
import datetime


def _clamp_gaussian(mean, sigma, lo, hi):
    """Sample a clamped Gaussian (Box-Muller) within [lo, hi]."""
    while True:
        u1 = random.random()
        u2 = random.random()
        val = mean + sigma * math.sqrt(-2.0 * math.log(u1 + 1e-12)) * math.cos(
            2.0 * math.pi * u2
        )
        if lo <= val <= hi:
            return val


class ActivityScheduler:
    """
    Scheduler that generates bursts of activity separated by pauses.

    Burst = block of mouse/keyboard events (each separated by a short interval).
    After each burst there is a pause; after N bursts there is a longer pause
    simulating a coffee/bathroom break.

    Parameters (all in minutes unless noted):
      burst_min, burst_max         — duration of an activity burst
      pause_min, pause_max         — short pause between bursts
      long_pause_min, long_pause_max — long pause every K bursts
      burst_trigger_range          — (K_low, K_high) bursts before long pause
      move_interval_mean           — seconds between moves inside a burst
      move_interval_sigma          — std dev of that interval
      move_interval_min, _max       — clamp bounds in seconds
    """

    def __init__(
        self,
        burst_min=5,
        burst_max=15,
        pause_min=2,
        pause_max=5,
        long_pause_min=10,
        long_pause_max=20,
        burst_trigger_range=(3, 5),
        move_interval_mean=45,
        move_interval_sigma=12,
        move_interval_min=15,
        move_interval_max=120,
    ):
        self.burst_min = burst_min
        self.burst_max = burst_max
        self.pause_min = pause_min
        self.pause_max = pause_max
        self.long_pause_min = long_pause_min
        self.long_pause_max = long_pause_max
        self.burst_trigger_lo, self.burst_trigger_hi = burst_trigger_range
        self.move_interval_mean = move_interval_mean
        self.move_interval_sigma = move_interval_sigma
        self.move_interval_min = move_interval_min
        self.move_interval_max = move_interval_max

        self._burst_count = 0
        self._bursts_until_long = random.randint(
            self.burst_trigger_lo, self.burst_trigger_hi
        )

    def time_of_day_factor(self, dt=None):
        """
        Return a multiplier ∈ [0, 1] for activity level based on time of day.

        Times (24h):
          08:00 – 11:00   → 1.0   (high)
          12:00 – 14:00   → 0.3   (lunch dip)
          14:00 – 17:00   → 1.0   (high)
          All other hours  → 0.15  (very low — simulating off-hours)

        Default: uses current local time.
        """
        if dt is None:
            dt = datetime.datetime.now()

        hour = dt.hour
        minute = dt.minute
        fractional_hour = hour + minute / 60.0

        if 8.0 <= fractional_hour < 11.0:
            return 1.0
        elif 12.0 <= fractional_hour < 14.0:
            return 0.3
        elif 14.0 <= fractional_hour < 17.0:
            return 1.0
        else:
            return 0.15

    def next_activity_interval(self, factor=1.0):
        """
        Time (in seconds) to wait before the next mouse/keyboard action
        inside a burst. Scaled by time-of-day factor.
        """
        base = _clamp_gaussian(
            self.move_interval_mean,
            self.move_interval_sigma,
            self.move_interval_min,
            self.move_interval_max,
        )
        # longer intervals = less activity when factor < 1
        scaled = base / max(factor, 0.05)
        return scaled

    def next_burst_duration(self):
        """Duration (in minutes) of the next activity burst."""
        return random.uniform(self.burst_min, self.burst_max)

    def next_pause_duration(self):
        """Duration (in minutes) of the next pause between bursts."""
        self._burst_count += 1
        if self._burst_count >= self._bursts_until_long:
            self._burst_count = 0
            self._bursts_until_long = random.randint(
                self.burst_trigger_lo, self.burst_trigger_hi
            )
            return self._next_long_pause()
        return random.uniform(self.pause_min, self.pause_max)

    def _next_long_pause(self):
        """Duration (in minutes) of a long pause."""
        return random.uniform(self.long_pause_min, self.long_pause_max)

    def reset(self):
        """Reset internal burst counter."""
        self._burst_count = 0
        self._bursts_until_long = random.randint(
            self.burst_trigger_lo, self.burst_trigger_hi
        )

    def active_now(self, factor=None):
        """
        Returns True if the scheduler considers this a reasonable time to act.
        Uses time_of_day_factor; if factor < 0.1 returns False.
        """
        if factor is None:
            factor = self.time_of_day_factor()
        return factor >= 0.1
