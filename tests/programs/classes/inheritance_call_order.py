# Dynamic dispatch and bound-method creation evaluate their receiver once, before arguments.
from typing import Callable


class Base:
    def __init__(self, n: int) -> None:
        self.n = n

    def add(self, n: int) -> int:
        return self.n + n

    def forward(self, n: int) -> int:
        return self.add(n)


class Derived(Base):
    def add(self, n: int) -> int:
        return super().add(n) * 10


events: list[str] = []
obj: Base = Derived(2)


def receiver() -> Base:
    events.append("receiver")
    return obj


def argument() -> int:
    events.append("argument")
    return 3


print(receiver().add(argument()), events)
events.clear()
print(receiver().forward(argument()), events)
events.clear()
bound: Callable[[int], int] = receiver().add
print(events)
print(bound(argument()), events)
events.clear()
print(Base.add(receiver(), argument()), events)
events.clear()
print(Base.forward(receiver(), argument()), events)
