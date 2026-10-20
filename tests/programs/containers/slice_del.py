# del of list slices, plain and stepped, as CPython's list_ass_subscript deletes them: bounds
# clamped as slice.indices() clamps them, either step sign, empty slices deleting nothing, and a
# step of 0 raising ValueError once the list and the bounds are evaluated.
from typing import TypeVar

T = TypeVar("T")


def say(v: int) -> int:
    print("say", v)
    return v


def fresh() -> list[int]:
    return list(range(10))


for lo, hi, st in [(None, None, 2), (1, None, 2), (None, None, -2), (None, None, -3), (8, 1, -3), (1, 8, -3),
                   (-3, None, None), (None, -7, 3), (100, None, -4), (-100, 100, 4), (5, 5, None), (0, 10, 11),
                   (9, -11, -1), (None, None, 9223372036854775807), (None, None, -9223372036854775807 - 1)]:
    xs = fresh()
    del xs[lo:hi:st]
    print(lo, hi, st, xs)

xs = fresh()
del xs[2:5]
print(xs)
del xs[-2:]
print(xs)
del xs[5:1]
print(xs)
del xs[:1], xs[::2]
print(xs)
del xs[:]
print(xs, len(xs))
del xs[:]
del xs[::-1]
xs.append(1)
print(xs)

ws = ["a", "b", "c", "d", "e"]
del ws[::2]
print(ws)
grid = [[1, 2, 3], [4, 5, 6]]
del grid[1][::-2]
del grid[:1]
print(grid)


def drop(xs: list[int], a: int, b: int, c: int) -> list[int]:
    del xs[a:b:c]
    return xs


for c in [1, 2, -1, -2, 0]:
    try:
        print(drop(fresh(), 2, 8, c))
    except ValueError as e:
        print("ValueError", e)

order = fresh()


def target() -> list[int]:
    print("target")
    return order


try:
    del target()[say(1) : say(5) : say(0)]
except ValueError as e:
    print("ValueError", e)
del target()[say(1) : say(9) : say(3)]
print(order)
maybe: list[int] | None = None
try:
    del maybe[say(0) :]
except TypeError as e:
    print("TypeError", e)


def thin(xs: list[T]) -> list[T]:
    del xs[1::2]
    return xs


print(thin([1, 2, 3, 4, 5]), thin(["p", "q"]), thin([1.5]))


class Queue:
    def __init__(self) -> None:
        self.items = [1, 2, 3, 4, 5, 6]

    def take(self, n: int) -> list[int]:
        out = self.items[:n]

        def trim() -> None:
            del self.items[:n]

        trim()
        return out


q = Queue()
print(q.take(2), q.take(3), q.items, q.take(5), q.items)

# a key function that empties the list being sorted
srt = [3, 1, 2]


def key(x: int) -> int:
    del srt[:]
    return x


srt.sort(key=key)
print(srt)
srt2 = [3, 1, 2]


def key2(x: int) -> int:
    del srt2[::2]
    return x


srt2.sort(key=key2)
print(srt2)
