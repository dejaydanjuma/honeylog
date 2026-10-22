"""Per-user epsilon ledger with a rolling window.

A user may spend at most `daily_epsilon` per `window` seconds. The ledger is
the source of truth for the number the dashboard renders, so it refuses a
sync that would exceed the cap rather than silently truncating it.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

DAY_SECONDS: float = 86_400.0


class BudgetExceeded(Exception):
    def __init__(self, requested: float, available: float) -> None:
        self.requested = requested
        self.available = available
        super().__init__(
            f"requested epsilon {requested:.3f} exceeds available {available:.3f}"
        )


@dataclass
class _Entry:
    ts: float
    epsilon: float


@dataclass
class BudgetLedger:
    daily_epsilon: float = 0.8
    window: float = DAY_SECONDS
    clock: Callable[[], float] = time.time
    _entries: list[_Entry] = field(default_factory=list)

    def active_entries(self, now: float | None = None) -> list[_Entry]:
        now = self.clock() if now is None else now
        self._prune(now)
        return list(self._entries)

    def _prune(self, now: float) -> None:
        cutoff = now - self.window
        self._entries = [e for e in self._entries if e.ts > cutoff]

    def spent(self, now: float | None = None) -> float:
        now = self.clock() if now is None else now
        self._prune(now)
        return sum(e.epsilon for e in self._entries)

    def available(self, now: float | None = None) -> float:
        return max(0.0, self.daily_epsilon - self.spent(now))

    def charge(self, epsilon: float, now: float | None = None) -> None:
        if epsilon <= 0:
            raise ValueError("epsilon must be positive")
        now = self.clock() if now is None else now
        remaining = self.available(now)
        if epsilon > remaining + 1e-9:
            raise BudgetExceeded(epsilon, remaining)
        self._entries.append(_Entry(ts=now, epsilon=epsilon))

    def snapshot(self, now: float | None = None) -> dict[str, float]:
        now = self.clock() if now is None else now
        spent = self.spent(now)
        return {
            "spent": spent,
            "remaining": max(0.0, self.daily_epsilon - spent),
            "daily_limit": self.daily_epsilon,
            "window_seconds": self.window,
        }