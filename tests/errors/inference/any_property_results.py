# error: overrides of Base.value() return incompatible types
from typing import Any


class Base:
    @property
    def value(self) -> Any:
        return 1


class Derived(Base):
    @property
    def value(self) -> Any:
        return "one"


def read(obj: Base):
    return obj.value


print(read(Derived()))
