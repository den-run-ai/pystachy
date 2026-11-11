from typing import Iterable


class Holder:
    def __init__(self, xs: list[int]):
        self.values = enumerate(xs, 4)
        self.reverse = reversed(xs)
        self.pairs = zip(xs, ["a", "b", "c"])


def first(xs: Iterable[int]) -> int:
    return next(iter(xs))


h = Holder([10, 20, 30])
print(next(h.values), list(h.values))
print(next(h.reverse), list(h.reverse))
print(next(h.pairs), list(h.pairs))
print(first(map(lambda x: x + 1, [7, 8])))
