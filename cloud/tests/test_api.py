import random

import pytest
from fastapi.testclient import TestClient

from app.budget import DAY_SECONDS
from app.main import create_app
from app.store import InMemoryStore


class FakeClock:
    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def client(clock):
    store = InMemoryStore(clock=clock)
    app = create_app(store=store, clock=clock, rng_factory=lambda: random.Random(0))
    return TestClient(app)


def payload(**over):
    base = {
        "user_id": "u1",
        "histogram": {"person": 4, "commitment": 2, "ambient": 9},
        "epsilon": 0.4,
    }
    base.update(over)
    return base


def test_sync_happy_path(client):
    r = client.post("/sync", json=payload())
    assert r.status_code == 200
    body = r.json()
    assert set(body["noisy_histogram"]) == {"person", "commitment", "ambient"}
    assert body["budget"]["spent"] == pytest.approx(0.4)
    assert body["budget"]["remaining"] == pytest.approx(0.4)


def test_budget_exhaustion_returns_429(client):
    assert client.post("/sync", json=payload(epsilon=0.6)).status_code == 200
    r = client.post("/sync", json=payload(epsilon=0.4))
    assert r.status_code == 429
    detail = r.json()["detail"]
    assert detail["error"] == "privacy_budget_exhausted"
    assert detail["available"] == pytest.approx(0.2)


def test_budget_recovers_after_window(client, clock):
    assert client.post("/sync", json=payload(epsilon=0.8)).status_code == 200
    assert client.post("/sync", json=payload(epsilon=0.1)).status_code == 429
    clock.t += DAY_SECONDS + 1
    assert client.post("/sync", json=payload(epsilon=0.8)).status_code == 200


def test_unknown_bucket_rejected(client):
    r = client.post("/sync", json=payload(histogram={"bogus": 1}))
    assert r.status_code == 422


def test_negative_count_rejected(client):
    r = client.post("/sync", json=payload(histogram={"person": -1}))
    assert r.status_code == 422


def test_epsilon_above_request_cap_rejected(client):
    r = client.post("/sync", json=payload(epsilon=2.0))
    assert r.status_code == 422


def test_ledger_endpoint_reflects_spend(client):
    client.post("/sync", json=payload(epsilon=0.3))
    r = client.get("/ledger/u1")
    assert r.status_code == 200
    assert r.json()["spent"] == pytest.approx(0.3)


def test_ledger_is_per_user(client):
    client.post("/sync", json=payload(user_id="a", epsilon=0.5))
    assert client.get("/ledger/b").json()["spent"] == pytest.approx(0.0)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}