from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import final, override as overrides
import typing as types
import typing_extensions as extensions


@final
def increment(value: int) -> int:
    return value + 1


@extensions.final
@dataclass
class Point:
    x: int


class Base(ABC):
    @abstractmethod
    def value(self) -> int:
        return 0


@types.final
class Concrete(Base):
    @overrides
    @final
    def value(self) -> int:
        return 7

    @final
    @staticmethod
    def first(value: int) -> int:
        return value + 10

    @staticmethod
    @extensions.override
    def second(value: int) -> int:
        return value + 20

    @types.final
    @classmethod
    def third(cls, value: int) -> int:
        return value + 30

    @classmethod
    @overrides
    def fourth(cls, value: int) -> int:
        return value + 40

    @final
    @property
    def fifth(self) -> int:
        return 50

    @property
    @overrides
    def sixth(self) -> int:
        return 60


# Markers carry no runtime inheritance restriction.
class Derived(Concrete):
    @extensions.override
    def value(self) -> int:
        return 8


def read(value: Base) -> int:
    return value.value()


obj = Concrete()
print(increment(1), Point(3).x, read(obj), read(Derived()))
print(obj.first(1), Concrete.second(2), obj.third(3), Concrete.fourth(4))
print(obj.fifth, obj.sixth)
