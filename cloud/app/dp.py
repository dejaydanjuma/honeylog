"""Differential-privacy primitives for Honeylog's sync path.

The only thing that leaves the device is a per-day histogram of salience
buckets. A single user contributes at most 1 to exactly one bucket, so the
L1 sensitivity of the histogram is 1.

Reference: Dwork & Roth, "The Algorithmic Foundations of Differential
Privacy", §3.3 (the Laplace mechanism).
"""
from __future__ import annotations

import math
import random
from typing import Mapping

# One user changes one bucket by one count.
SENSITIVITY: float = 1.0


def laplace_scale(epsilon: float, sensitivity: float = SENSITIVITY) -> float:
    """Noise scale b = Δf / ε."""
    if epsilon <= 0:
        raise ValueError("epsilon must be positive")
    if sensitivity <= 0:
        raise ValueError("sensitivity must be positive")
    return sensitivity / epsilon


def laplace_sample(scale: float, rng: random.Random | None = None) -> float:
    """Draw from Laplace(0, scale) via inverse-CDF sampling."""
    rng = rng or random.Random()
    u = rng.random() - 0.5
    # u in (-0.5, 0.5) -> x = -b * sign(u) * ln(1 - 2|u|)
    return -scale * math.copysign(1.0, u) * math.log(1.0 - 2.0 * abs(u))


def add_noise(
    histogram: Mapping[str, int],
    epsilon: float,
    rng: random.Random | None = None,
) -> dict[str, int]:
    """Return the histogram with Laplace noise added per bucket.

    Counts are clamped at zero. Clamping is a deterministic function of the
    noisy output, so by post-processing immunity it preserves the guarantee.
    """
    scale = laplace_scale(epsilon)
    rng = rng or random.Random()
    return {
        bucket: max(0, int(round(count + laplace_sample(scale, rng))))
        for bucket, count in histogram.items()
    }