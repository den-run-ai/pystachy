from typing import Any, Annotated
from typing import Any as Unknown
import typing as types


class Box:
    def __init__(self, values: list[str]) -> None:
        self.values = values

    @property
    def value(self) -> Any:
        return self.values

    @value.setter
    def value(self, value: list[str]) -> None:
        self.values = value

    @value.deleter
    def value(self) -> None:
        self.values.clear()

    @property
    def size(self) -> "types.Any":
        return len(self.values)

    @property
    def first(self) -> Annotated[Unknown, "inferred"]:
        return self.values[0]


class Base:
    @property
    def amount(self) -> Any:
        return 10


class Derived(Base):
    @property
    def amount(self) -> types.Any:
        return 20


def read(value: Base) -> int:
    return value.amount


values = ["one", "two"]
obj = Box(values)
alias = obj.value
print(alias is values, obj.size, obj.first)
alias.append("three")
print(obj.value, obj.size)
obj.value = ["new"]
print(alias, obj.value)
del obj.value
print(obj.value, alias)
print(read(Base()), read(Derived()))
