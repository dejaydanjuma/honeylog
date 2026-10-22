import random

import pytest

from app.dp import SENSITIVITY, add_noise, laplace_sample, laplace_scale


def test_scale_is_sensitivity_over_epsilon():
    assert laplace_scale(0.8) == pytest.approx(SENSITIVITY / 0.8)


@pytest.mark.parametrize("eps", [0, -1])
def test_non_positive_epsilon_rejected(eps):
    with pytest.raises(ValueError):
        laplace_scale(eps)


def test_laplace_mean_is_zero():
    rng = random.Random(1234)
    samples = [laplace_sample(2.0, rng) for _ in range(40_000)]
    mean = sum(samples) / len(samples)
    assert abs(mean) < 0.05 * 2.0  # well under one tenth of a scale


def test_laplace_variance_matches_theory():
    rng = random.Random(99)
    scale = 1.5
    samples = [laplace_sample(scale, rng) for _ in range(40_000)]
    mean = sum(samples) / len(samples)
    var = sum((s - mean) ** 2 for s in samples) / len(samples)
    assert var == pytest.approx(2 * scale**2, rel=0.10)


def test_add_noise_preserves_keys_and_non_negative():
    rng = random.Random(7)
    hist = {"person": 5, "ambient": 0, "commitment": 1}
    out = add_noise(hist, 0.8, rng=rng)
    assert set(out) == set(hist)
    assert all(v >= 0 for v in out.values())
    assert all(isinstance(v, int) for v in out.values())


def test_noise_actually_perturbs():
    hist = {"person": 100, "ambient": 100}
    rng = random.Random(42)
    outs = [add_noise(hist, 0.8, rng=rng) for _ in range(10)]
    assert any(o != hist for o in outs)