"""Ledger storage.

InMemoryStore for local dev and tests; DynamoStore for Lambda. The Protocol is
the seam: handlers call ledger_for() and persist() without knowing which is
behind them.
"""
from __future__ import annotations

import time
from typing import Callable, Protocol

from .budget import BudgetLedger


class LedgerStore(Protocol):
    def ledger_for(self, user_id: str) -> BudgetLedger: ...
    def persist(self, user_id: str, ledger: BudgetLedger) -> None: ...


class InMemoryStore:
    """Per-user ledgers in a dict. Not durable; fine for local dev and tests."""

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

    def persist(self, user_id: str, ledger: BudgetLedger) -> None:
        return  # already held in process memory


class DynamoStore:
    """DynamoDB-backed ledger. One item per user: {pk, charges: [{ts, epsilon}]}.

    Charges are stored as strings because DynamoDB rejects floats; they're
    parsed back on load. Entries older than the window are pruned before write,
    so the item stays small.
    """

    def __init__(
        self,
        table_name: str,
        daily_epsilon: float = 0.8,
        clock: Callable[[], float] = time.time,
        table=None,
    ) -> None:
        self._daily = daily_epsilon
        self._clock = clock
        if table is None:
            import boto3  # imported lazily so tests don't need it

            table = boto3.resource("dynamodb").Table(table_name)
        self._table = table
        self._cache: dict[str, BudgetLedger] = {}

    def ledger_for(self, user_id: str) -> BudgetLedger:
        if user_id in self._cache:
            return self._cache[user_id]

        led = BudgetLedger(daily_epsilon=self._daily, clock=self._clock)
        item = self._table.get_item(Key={"pk": user_id}).get("Item") or {}
        for e in item.get("charges", []):
            try:
                led.charge(float(e["epsilon"]), now=float(e["ts"]))
            except Exception:
                # Expired or over-cap historical entry; skip rather than fail.
                pass
        self._cache[user_id] = led
        return led

    def persist(self, user_id: str, ledger: BudgetLedger) -> None:
        now = self._clock()
        self._table.put_item(
            Item={
                "pk": user_id,
                "charges": [
                    {"ts": str(e.ts), "epsilon": str(e.epsilon)}
                    for e in ledger.active_entries(now)
                ],
                "updated": str(now),
            }
        )