# pystachy: dynamic-any
# Repeated crossings keep exact union tags and evaluate each source once,
# including after exception and finally joins.
from typing import Any


class Cell:
    def __init__(self) -> None:
        self.value: bool | int | str | None = None


def source(value: Any, events: list[str], label: str) -> Any:
    events.append(label)
    return value


def describe(value: Any) -> str:
    return type(value).__name__ + ":" + repr(value)


def relay(value: bool | int | str | None) -> bool | int | str | None:
    return value


def run() -> None:
    values: list[Any] = [True, 1, False, 0, "001", None, int("1001")]
    events: list[str] = []
    cell = Cell()
    for i in range(len(values)):
        slot: bool | int | str | None = source(values[i], events, "local")
        cell.value = source(slot, events, "field")
        try:
            if i % 2:
                slot = relay(source(cell.value, events, "call"))
                raise ValueError("rejoin")
        except ValueError:
            print("caught", describe(slot))
        finally:
            print("finally", describe(cell.value))
        copied: Any = relay(slot)
        print("joined", describe(copied), copied is values[i], len(events))
    print(events)


run()
