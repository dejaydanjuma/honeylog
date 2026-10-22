import pytest

from app.budget import DAY_SECONDS
from app.store import DynamoStore


class FakeTable:
    """Minimal DynamoDB Table stand-in: dict of pk -> Item."""

    def __init__(self) -> None:
        self.items: dict[str, dict] = {}

    def get_item(self, Key):  # noqa: N803 - matches boto3's API
        item = self.items.get(Key["pk"])
        return {"Item": item} if item else {}

    def put_item(self, Item):  # noqa: N803
        self.items[Item["pk"]] = Item


class FakeClock:
    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


def test_charges_persist_across_store_instances():
    table, clock = FakeTable(), FakeClock()

    a = DynamoStore("t", clock=clock, table=table)
    a.ledger_for("u1").charge(0.4)
    a.persist("u1", a.ledger_for("u1"))

    b = DynamoStore("t", clock=clock, table=table)   # fresh process
    assert b.ledger_for("u1").spent() == pytest.approx(0.4)


def test_roundtrip_refuses_after_reload():
    table, clock = FakeTable(), FakeClock()

    a = DynamoStore("t", clock=clock, table=table)
    led = a.ledger_for("u1")
    led.charge(0.8)
    a.persist("u1", led)

    b = DynamoStore("t", clock=clock, table=table)
    with pytest.raises(Exception):
        b.ledger_for("u1").charge(0.1)


def test_expired_charges_pruned_on_persist():
    table, clock = FakeTable(), FakeClock()

    a = DynamoStore("t", clock=clock, table=table)
    a.ledger_for("u1").charge(0.4)
    a.persist("u1", a.ledger_for("u1"))

    clock.t += DAY_SECONDS + 1
    a.persist("u1", a.ledger_for("u1"))   # ledger_for cached, but persist re-prunes

    assert table.items["u1"]["charges"] == []