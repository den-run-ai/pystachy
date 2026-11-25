# Replay concrete template dependencies before compiling base-typed dispatch.
# Item[str] is encountered first in source; the next declaration pass recreates
# Item[int] first, so a late request must not retain the old Item-2 type name.
from typing import Generic, TypeVar

T = TypeVar("T")


class Typed(Generic[T]):
    def __init__(self, value: T) -> None:
        self.value = value


class Item:
    def __init__(self, value):
        self.value = value


class Base:
    def __init__(self, value):
        self.value = value

    @classmethod
    def make(cls, value):
        return cls(value)

    @classmethod
    def name(cls) -> str:
        return cls.__name__


class Sub(Base):
    def __init__(self, value: str) -> None:
        super().__init__(value)


def report(value: Base) -> str:
    return value.name()


first = Item("first")
argument = Item(1)
held = [Base(argument)]
print(report(held[0]))
created = Sub("seed").make(argument)
held.append(created)
print(report(held[1]), type(created).__name__, created.value is argument)
created.value.value += 1
print(first.value, argument.value)
items = [argument]
wrapped = Sub("list").make(items)
print(type(wrapped).__name__, wrapped.value is items, wrapped.value[0] is argument)
typed: Typed[int] = Typed(7)
named = Sub("generic").make(typed)
print(type(named).__name__, named.value is typed, named.value.value)
