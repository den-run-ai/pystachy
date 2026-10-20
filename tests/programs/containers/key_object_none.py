# A key that is None when sorted(), list.sort(), min() or max() runs is no key, as key=None is
# (#506): a key object (an instance of a class that defines __call__) that may be None, and a
# Callable | None, order the items themselves then, and are called where they are not None.
# (Items that are objects keep the call: see tests/deviations/key_object_none_unordered.py.)
import bisect
from operator import itemgetter
from typing import Callable


class Second:
    def __call__(self, t: tuple[int, str]) -> str:
        return t[1]


class Holder:
    def __init__(self) -> None:
        self.key: Second | None = Second()


class Neg:
    def __call__(self, x: int) -> int:
        print("key", x)
        return -x


class Count:
    def __init__(self, n: int) -> None:
        self.n = n

    def __iter__(self) -> "CountIter":
        return CountIter(self.n)


class CountIter:
    def __init__(self, n: int) -> None:
        self.i = 0
        self.n = n

    def __next__(self) -> int:
        if self.i == self.n:
            raise StopIteration
        self.i += 1
        return (self.i * 7) % 5


h = Holder()
xs = [(2, "a"), (1, "b")]
print(sorted(xs, key=h.key), min(xs, key=h.key))
h.key = None
print(sorted(xs, key=h.key), min(xs, key=h.key), max(xs, key=h.key), min((3, "z"), (1, "y"), key=h.key))
ys = list(xs)
ys.sort(key=h.key)
print(ys)

getter = itemgetter(1)
print(sorted([(2, "b"), (1, "a")], key=getter))
getter = None
print(sorted([(2, "b"), (1, "a")], key=getter))


def run(key: Neg | None) -> None:
    zs = [3, 1, 2]
    zs.sort(key=key, reverse=True)
    print(sorted([3, 1, 2], key=key), zs)
    print(min(Count(4), key=key), max(Count(4), key=key), min(5, 3, 8, key=key), max([7, 9, 8], key=key))
    try:
        print(min(zs[:0], key=key))
    except ValueError as e:
        print("ValueError:", e)


run(Neg())
run(None)


def neg(x: int) -> int:
    return -x


c: Callable[[int], int] | None = neg
print(sorted([3, 1, 2], key=c), min([3, 1, 2], key=c), max(3, 1, 2, key=c))
c = None
print(sorted([3, 1, 2], key=c), min([3, 1, 2], key=c), max(3, 1, 2, key=c))
ws = [3, 1, 2]
ws.sort(key=c, reverse=True)
print(ws)

nk: Neg | None = None
print(bisect.bisect([1, 3, 5], 4, key=nk), bisect.bisect_left([1, 3, 5], 3, key=nk))
