import pytest

from app.budget import DAY_SECONDS, BudgetExceeded, BudgetLedger


class FakeClock:
    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def test_charge_accumulates():
    clock = FakeClock()
    led = BudgetLedger(clock=clock)
    led.charge(0.3)
    led.charge(0.2)
    assert led.spent() == pytest.approx(0.5)
    assert led.available() == pytest.approx(0.3)


def test_exceeding_cap_raises_with_available_amount():
    clock = FakeClock()
    led = BudgetLedger(daily_epsilon=0.8, clock=clock)
    led.charge(0.6)
    with pytest.raises(BudgetExceeded) as exc:
        led.charge(0.5)
    assert exc.value.available == pytest.approx(0.2)
    assert exc.value.requested == pytest.approx(0.5)
    assert led.spent() == pytest.approx(0.6)  # rejected charge not recorded


def test_window_expiry_frees_budget():
    clock = FakeClock()
    led = BudgetLedger(daily_epsilon=0.8, clock=clock)
    led.charge(0.8)
    assert led.available() == pytest.approx(0.0)
    clock.advance(DAY_SECONDS + 1)
    assert led.available() == pytest.approx(0.8)


def test_partial_window_expiry():
    clock = FakeClock()
    led = BudgetLedger(daily_epsilon=0.8, clock=clock)
    led.charge(0.4)
    clock.advance(DAY_SECONDS / 2)
    led.charge(0.4)
    assert led.spent() == pytest.approx(0.8)
    clock.advance(DAY_SECONDS / 2 + 1)  # first charge aged out, second retained
    assert led.spent() == pytest.approx(0.4)


def test_non_positive_charge_rejected():
    led = BudgetLedger(clock=FakeClock())
    with pytest.raises(ValueError):
        led.charge(0)