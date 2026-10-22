"""FastAPI surface for the Honeylog sync path.

Two endpoints:
  POST /sync          accept a salience histogram, charge epsilon, return noisy counts
  GET  /ledger/{id}   current spend for a user (what the dashboard renders)

Storage is selected at startup: an explicit `store` argument wins, then the
HONEYLOG_TABLE environment variable (DynamoDB, used in Lambda), then an
in-memory store (local dev and tests).
"""
from __future__ import annotations

import os
import random
import time
from typing import Callable

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from .budget import BudgetExceeded, BudgetLedger
from .dp import add_noise
from .store import DynamoStore, InMemoryStore, LedgerStore

# Must match Category in core/src/lib.rs
ALLOWED_BUCKETS = {"person", "commitment", "location", "object", "ambient"}


class SyncRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    histogram: dict[str, int]
    epsilon: float = Field(gt=0, le=1.0)

    @field_validator("histogram")
    @classmethod
    def check_histogram(cls, v: dict[str, int]) -> dict[str, int]:
        unknown = set(v) - ALLOWED_BUCKETS
        if unknown:
            raise ValueError(f"unknown buckets: {sorted(unknown)}")
        if any(c < 0 for c in v.values()):
            raise ValueError("counts must be non-negative")
        return v


class BudgetView(BaseModel):
    spent: float
    remaining: float
    daily_limit: float
    window_seconds: float


class SyncResponse(BaseModel):
    noisy_histogram: dict[str, int]
    budget: BudgetView


def create_app(
    store: LedgerStore | None = None,
    clock: Callable[[], float] = time.time,
    rng_factory: Callable[[], random.Random] = random.Random,
) -> FastAPI:
    app = FastAPI(title="honeylog-sync", version="0.1.0")

    if store is not None:
        ledger_store: LedgerStore = store
    elif os.environ.get("HONEYLOG_TABLE"):
        ledger_store = DynamoStore(os.environ["HONEYLOG_TABLE"], clock=clock)
    else:
        ledger_store = InMemoryStore(clock=clock)

    @app.post("/sync", response_model=SyncResponse)
    def sync(req: SyncRequest) -> SyncResponse:
        ledger: BudgetLedger = ledger_store.ledger_for(req.user_id)
        try:
            ledger.charge(req.epsilon)
        except BudgetExceeded as e:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "privacy_budget_exhausted",
                    "requested": e.requested,
                    "available": e.available,
                },
            )
        ledger_store.persist(req.user_id, ledger)
        noisy = add_noise(req.histogram, req.epsilon, rng=rng_factory())
        return SyncResponse(noisy_histogram=noisy, budget=BudgetView(**ledger.snapshot()))

    @app.get("/ledger/{user_id}", response_model=BudgetView)
    def ledger_view(user_id: str) -> BudgetView:
        return BudgetView(**ledger_store.ledger_for(user_id).snapshot())

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()