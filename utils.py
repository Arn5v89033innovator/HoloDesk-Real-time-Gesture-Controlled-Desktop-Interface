"""
utils.py
========
Shared utility helpers: colour math, easing, geometry, smooth values.
"""

import math
import time


# ──────────────────────────────────────────────────────────────────────
# Colour helpers (all values 0-255)

def lerp_color(c1: tuple, c2: tuple, t: float) -> tuple:
    """Linearly interpolate between two RGB tuples."""
    t = max(0.0, min(1.0, t))
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def alpha_blend(color: tuple, alpha: float) -> tuple:
    """Return (r, g, b, a) with given alpha 0-1."""
    return (*color[:3], int(alpha * 255))


def ease_in_out(t: float) -> float:
    """Smooth-step easing function."""
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


# ──────────────────────────────────────────────────────────────────────
# Geometry

def angle_between(cx: float, cy: float, px: float, py: float) -> float:
    """Angle in degrees from centre to point, measured from +x axis."""
    return math.degrees(math.atan2(py - cy, px - cx))


def point_on_circle(cx: float, cy: float, r: float, deg: float
                    ) -> tuple[float, float]:
    rad = math.radians(deg)
    return cx + r * math.cos(rad), cy + r * math.sin(rad)


def dist2d(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)


# ──────────────────────────────────────────────────────────────────────
class SmoothValue:
    """Exponential moving average for smoothing noisy input values."""

    def __init__(self, initial: float = 0.0, smoothing: float = 0.2):
        self.value = initial
        self.smoothing = smoothing  # lower = smoother but more lag

    def update(self, new_value: float) -> float:
        self.value = self.value + self.smoothing * (new_value - self.value)
        return self.value


class SmoothPoint:
    """Smooth 2-D point."""

    def __init__(self, x: float = 0, y: float = 0, smoothing: float = 0.2):
        self.x = SmoothValue(x, smoothing)
        self.y = SmoothValue(y, smoothing)

    def update(self, x: float, y: float) -> tuple[float, float]:
        return self.x.update(x), self.y.update(y)

    @property
    def pos(self) -> tuple[float, float]:
        return self.x.value, self.y.value


# ──────────────────────────────────────────────────────────────────────
class Timer:
    """Simple elapsed-time helper."""

    def __init__(self):
        self._start = time.perf_counter()

    def elapsed(self) -> float:
        return time.perf_counter() - self._start

    def reset(self):
        self._start = time.perf_counter()
