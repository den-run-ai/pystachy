# pystachy: dynamic-any
# No typed construction or boxed exemplar establishes any of these layouts.
from typing import Any


class Empty:
    pass


class Record:
    def __init__(self, value: int, /, label: str = "default", *, enabled: bool = True) -> None:
        self.value = value
        self.label = label
        self.enabled = enabled


class Defaults:
    value: int = 1000
    label: str = "class"


factories: list[Any] = [Empty, Record, Defaults]
empty = factories[0]()
another = factories[0]()
print(type(empty) is Empty, type(another) is Empty, empty is another)

number = int("123456")
record = factories[1](number)
changed = factories[1](number, label="other", enabled=False)
print(type(record) is Record, record.value is number, record.label, record.enabled)
print(type(changed) is Record, changed.value is number, changed.label, changed.enabled)
print(record is changed)
record.value = 42
print(record.value, changed.value)

defaults = factories[2]()
print(type(defaults) is Defaults, defaults.value, defaults.label)
print(defaults.value is Defaults.value)
