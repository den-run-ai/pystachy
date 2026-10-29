# pystachy: dynamic-any
# Only this helper opts in. Each caller runs with ordinary ints and, in the python-int
# gate, with promoting ints; identity must survive the typed/dynamic boundary in both.
from typing import Any

kept: list[Any] = []


def keep(value: Any) -> None:
    kept.append(value)


def check(label: str) -> None:
    print(label, kept[0] is kept[1], id(kept[0]) == id(kept[1]), kept[0] == kept[1])
    kept.clear()


def fields(label: str, obj: Any, value: Any) -> None:
    print(label, obj.value is obj.value, obj.value is value, id(obj.value) == id(value))


def churn() -> None:
    for i in range(24):
        garbage: Any = [str(i), int("7654")]


def read_field(obj: Any) -> Any:
    return obj.value
