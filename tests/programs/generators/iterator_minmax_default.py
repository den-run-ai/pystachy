# Keys run between next calls and before a later iterator error.
from typing import Callable


class Source:
    def __init__(self, xs: list[int]):
        self.xs = xs
        self.index = 0

    def __iter__(self):
        print("iter")
        return self

    def __next__(self) -> int:
        index = self.index
        print("next", index)
        if index >= len(self.xs):
            raise StopIteration
        self.index = index + 1
        return self.xs[index]


def key(value: int) -> int:
    print("key", value)
    return -value


def default() -> int:
    print("default")
    return 100


def values():
    print("yield", 2)
    yield 2
    print("yield", 1)
    yield 1
    print("done")


print(min(Source([3, 2, 1]), key=key, default=default()))
print(max(Source([]), key=key, default=default()))
print(min(values(), key=key, default=0))
g = values()
print(max(g, default=None), list(g))
print(min(iter([4, 2, 3]), default=None))
empty: list[int] = []
print(min(iter(empty), default=1))


def optional(fn: Callable[[int], int] | None) -> int | None:
    return min(iter([4, 2, 3]), key=fn, default=None)


print(optional(key), optional(None))


def broken_key(value: int) -> int:
    raise ValueError("key first")


def later_error():
    yield 1
    raise RuntimeError("iterator later")


try:
    print(min(later_error(), key=broken_key, default=0))
except ValueError as error:
    print(str(error))


s = {1, 2, 3}


def clear_set(value: int) -> int:
    s.clear()
    return value


try:
    print(min(s, key=clear_set, default=0))
except RuntimeError as error:
    print(str(error))

s = {1, 2, 3}
try:
    print(max(s, key=clear_set))
except RuntimeError as error:
    print(str(error))


def items():
    print("item", 3)
    yield 3
    print("item", 1)
    yield 1


print(min(items(), key=key))


class Yielding:
    def __init__(self, values: list[list[int]]):
        self.values = values

    def __iter__(self):
        for value in self.values:
            yield value


print(min(Yielding([[3], [1]]), default=[]))
print(max(Yielding([]), default=[]))
