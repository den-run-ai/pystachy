# pystachy: dynamic-any
# The inherited initializer binds the subclass's call and preserves defaults.
from typing import Any


class Entry:
    def __init__(self, value: int, label: str = "default") -> None:
        self.value = value
        self.label = label


class Child(Entry):
    pass


class Config:
    def __init__(self, value: int, /, *, enabled: bool = True) -> None:
        self.value = value
        self.enabled = enabled


original: Any = Child(0)
config_original: Any = Config(0)
factory: Any = type(original)
first = factory(3)
second = factory(label="named", value=4)
third = factory(5, label="mixed")
for value in [first, second, third]:
    print(type(value) is Child, isinstance(value, Entry), value.value, value.label)
print(first is second, second is third)

config: Any = type(config_original)
print(config(6).enabled, config(7, enabled=False).enabled)
try:
    factory(label="missing")
except TypeError as exc:
    print(str(exc))
try:
    factory(1, unknown="bad")
except TypeError as exc:
    print(str(exc))
try:
    factory(1, value=2)
except TypeError as exc:
    print(str(exc))
try:
    config(value=8)
except TypeError as exc:
    print(str(exc))
try:
    config(9, False)
except TypeError as exc:
    print(str(exc))
