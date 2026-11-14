"""Test classes, fixture scopes and parameters, and pytest's common helpers.

Original cases for forms the generated runner accepts beyond plain functions.
They run unchanged under CPython pytest.
"""

import os
from typing import Iterator

import pytest


class QuotaError(Exception):
    def __init__(self, limit: int, used: int) -> None:
        super().__init__(f"quota of {limit} exceeded by {used - limit}")
        self.limit = limit
        self.used = used


class Meter:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.used = 0

    def charge(self, amount: int) -> int:
        if self.used + amount > self.limit:
            raise QuotaError(self.limit, self.used + amount)
        self.used += amount
        return self.limit - self.used


EVENTS: list[str] = []
rates = [(3, 0.3), (7, 0.7)]


@pytest.fixture(scope="module")
def ledger() -> Iterator[list[int]]:
    EVENTS.append("ledger opened")
    yield []
    EVENTS.append("ledger closed")


@pytest.fixture(scope="class")
def meter(ledger: list[int]) -> Meter:
    EVENTS.append("meter made")
    return Meter(10)


@pytest.fixture(params=[1, 4], ids=["small", "large"])
def amount(request) -> int:
    return request.param


class TestMeter:
    def test_charge(self, meter: Meter, amount: int, ledger: list[int]):
        remaining = meter.charge(amount)
        ledger.append(amount)
        assert remaining == 10 - sum(ledger)

    def test_class_scope_keeps_one_meter(self, meter: Meter, ledger: list[int]):
        assert meter.used == 5 and ledger == [1, 4]
        assert EVENTS == ["ledger opened", "meter made"]

    def test_quota_error_fields(self, meter: Meter):
        with pytest.raises(QuotaError, match="exceeded by 2") as failure:
            meter.charge(7)
        assert failure.value.limit == 10 and failure.value.used == 12
        assert failure.typename == "QuotaError"

    @pytest.mark.xfail(raises=QuotaError, reason="the meter is nearly full")
    def test_expected_quota_failure(self, meter: Meter):
        meter.charge(6)


@pytest.mark.parametrize("tenths,expected", rates)
class TestRates:
    def test_ratio(self, tenths: int, expected: float):
        assert tenths / 10 == pytest.approx(expected)
        assert tenths / 10 != pytest.approx(expected + 0.01)

    def test_tolerance(self, tenths: int, expected: float):
        assert tenths / 10 + 0.004 == pytest.approx(expected, abs=0.005)


def test_new_meter_outside_a_class(meter: Meter, ledger: list[int]):
    assert meter.used == 0 and len(ledger) == 2
    assert EVENTS.count("meter made") == 2


def test_number_errors():
    with pytest.raises((ValueError, ZeroDivisionError)) as failure:
        int("ten") // 0
    assert failure.type is ValueError
    assert failure.match("invalid literal")


def test_scratch_directory(tmp_path):
    report = tmp_path / "usage.txt"
    report.write_text("used=5\n")
    assert report.read_text() == "used=5\n"
    assert [item.name for item in tmp_path.iterdir()] == ["usage.txt"]


def test_environment_is_restored_after(monkeypatch):
    monkeypatch.setenv("PYSTACHY_EXAMPLE_METER", "on")
    assert os.environ["PYSTACHY_EXAMPLE_METER"] == "on"


def test_environment_was_restored():
    assert os.environ.get("PYSTACHY_EXAMPLE_METER") is None
