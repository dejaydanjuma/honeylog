"""Ledger storage. In-memory here; swap for DynamoDB without touching callers."""
from __future__ import annotations

import time
from typing import Callable, Protocol

from .budget import BudgetLedger


class LedgerStore(Protocol):
    def ledger_for(self, user_id: str) -> BudgetLedger: ...


class InMemoryStore:
    """Per-user ledgers held in a dict. Not durable; fine for local dev/tests."""

    def __init__(
        self,
        daily_epsilon: float = 0.8,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._daily = daily_epsilon
        self._clock = clock
        self._ledgers: dict[str, BudgetLedger] = {}

    def ledger_for(self, user_id: str) -> BudgetLedger:
        if user_id not in self._ledgers:
            self._ledgers[user_id] = BudgetLedger(
                daily_epsilon=self._daily, clock=self._clock
            )
        return self._ledgers[user_id]