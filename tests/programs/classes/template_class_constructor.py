# Calling the class of a template instance keeps the exact class, evaluates each operand
# once in source order, and treats None.__class__ as NoneType.
from typing import Generic, TypeVar

T = TypeVar('T')
events: list[str] = []


class Box(Generic[T]):
    def __init__(self, value: T) -> None:
        self.value = value
        events.append('init')


class Child(Box):
    pass


def receiver(x: Box[int] | None):
    events.append('receiver')
    return x


def argument() -> int:
    events.append('argument')
    return 2


for x in [Box(1), Child(3), None]:
    events.clear()
    try:
        y = receiver(x).__class__(argument())
        print(type(y).__name__, y.value)
    except TypeError as e:
        print(type(e).__name__, str(e))
    print(events)
