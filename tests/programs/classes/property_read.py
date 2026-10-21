from typing import Callable


def increment(x: int) -> int:
    print("call", x)
    return x + 1


class Meter:
    def __init__(self, n: int) -> None:
        self.n = n
        self.reads = 0
        self._items: list[int] = []
        self.saved = self.value
        self.result = self.callback(2)

    @property
    def value(self) -> int:
        self.reads += 1
        print("get", self.n)
        return self.n * 2

    @property
    def callback(self) -> Callable[[int], int]:
        print("callback")
        return increment

    @property
    def missing(self) -> int:
        raise AttributeError("unavailable")

    @property
    def items(self) -> list[int]:
        return self._items

    @property
    def broken_callback(self) -> Callable[[int], int]:
        raise AttributeError("no callback")

    def twice(self) -> int:
        return self.value + self.value


def receiver(n: int) -> Meter:
    print("receiver")
    return Meter(n)


def argument() -> int:
    print("argument")
    return 9


m = Meter(3)
print("fields", m.saved, m.result)
m.items.append(8)
print(m.items)
print(m.value, m.value, m.reads)
print(m.twice(), m.reads)
print(receiver(4).value)
print(receiver(5).callback(argument()))
f = m.callback
print(f(10))
try:
    print(m.missing)
except AttributeError as e:
    print("caught", str(e))
try:
    print(m.broken_callback(argument()))
except AttributeError as e:
    print("before argument", str(e))

missing: Meter = None
try:
    print(missing.value)
except AttributeError as e:
    print("none", str(e))
try:
    print(missing.callback(argument()))
except AttributeError as e:
    print("none before argument", str(e))
