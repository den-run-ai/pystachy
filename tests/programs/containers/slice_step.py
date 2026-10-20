# Stepped slices x[a:b:c] of lists, strs and tuples: CPython's slice.indices() clamping for every
# part omitted, None, negative or out of range, steps of either sign, a step of 0 raising
# ValueError once the bounds are evaluated, and fixed-shape tuples (constant bounds keep the item
# types; NamedTuples give plain tuples), in functions, methods, closures and templates.
from typing import NamedTuple, TypeVar

T = TypeVar("T")


def say(v: int) -> int:
    print("say", v)
    return v


xs = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
print(xs[::2], xs[1::2], xs[::-1], xs[::-3], xs[8:2:-2], xs[2:8:-2], xs[-2:-9:-3])
print(xs[::100], xs[::-100], xs[100::-4], xs[-100::4], xs[:-100:-4], xs[5:5:2], xs[5:6:-1])
print(xs[None:None:None], xs[None:None:-1], xs[3::None], xs[::1], xs[::-9223372036854775807 - 1])
print(xs[-9223372036854775807 - 1::-1], xs[:-9223372036854775807 - 1:-1], xs[9223372036854775807::-5])
print(xs[True::True], xs[False:-1:3], xs[0:9223372036854775807:9223372036854775807])

s = "abcdefghij"
print(s[::2], s[1::2], s[::-1], s[::-3], s[8:2:-2], s[2:8:-2], s[-2:-9:-3], s[::100])
print(repr(s[5:5:2]), repr(s[5:6:-1]), s[None:None:-1], s[::-9223372036854775807 - 1])
print(s[::1] is s, s[:100:1] is s, s[::-1][::-1] == s, s[1::1] == s[1:])

t = (1, "a", 2.5, True, None)
print(t[::2], t[1::2], t[::-1], t[3:0:-2], t[10:], t[-2:], t[::-100], t[:] is t, t[::1] is t)
print(t[4:1], t[1:4:-1], () [::-1], (7,)[::5])


class P(NamedTuple):
    x: int
    y: str
    z: float


p = P(1, "b", 3.5)
print(p[::-1], p[1:], p[:2], p[::2], p[:])


def counted(items: list[int]) -> tuple[int, ...]:
    return tuple(items)


vt = counted([10, 20, 30, 40, 50])
print(vt[::2], vt[1:4], vt[::-1], vt[4:0:-2], vt[7:], vt[:] is vt, vt[::1] is vt, len(vt[::3]))
names: tuple[str | None, ...] = ("a", None, "c")
print(names[::-1], names[1:])


def window(xs: list[int], a: int | None, b: int | None, c: int | None) -> list[int]:
    return xs[a:b:c]


print(window(xs, None, None, None), window(xs, 2, None, 3), window(xs, None, 2, -3), window(xs, -1, None, -4))


def by_step(st: int) -> None:
    try:
        print(xs[1:8:st], s[1:8:st], vt[1:8:st], (1, 2, 3, 4, 5)[1:4:st])
    except ValueError as e:
        print("ValueError", e)


for st in [1, 2, 3, -1, -2, 0, 7, -7]:
    by_step(st)


def fixed_step(t: tuple[int, int, int], i: int) -> tuple[int, ...]:
    return t[i::2]  # (bounds computed at run time: a tuple[int, ...] of the tuple's one item type)


print(fixed_step((1, 2, 3), 0), fixed_step((1, 2, 3), 1), fixed_step((1, 2, 3), -1))


def rest(n: int, *args: int) -> None:
    # (*args holds each call's arguments: items of one type, or none)
    try:
        print(args[n:], args[::n], args[n::-n])
    except ValueError as e:
        print("ValueError", e)


rest(1)
rest(1, 5, 6, 7)
rest(-2, 5, 6, 7)
rest(0)
rest(0, 1)

# a step of 0 raises once the object and the bounds are evaluated; None raises before it
try:
    print(xs[say(1):say(2):say(0)])
except ValueError as e:
    print("ValueError", e)
try:
    print(s[::say(0)])
except ValueError as e:
    print("ValueError", e)
try:
    print(t[::0])
except ValueError as e:
    print("ValueError", e)
try:
    print(vt[::0])
except ValueError as e:
    print("ValueError", e)
maybe: list[int] | None = None
try:
    print(maybe[say(0)::say(0)])
except TypeError as e:
    print("TypeError", e)
print(xs[say(7):say(1):say(-2)])


def rev(xs: list[T]) -> list[T]:
    return xs[::-1]


print(rev([1, 2, 3]), rev(["x", "y"]), rev([[1], [2, 3]]), rev([1.5, 2.5]))


class Buf:
    def __init__(self, data: str) -> None:
        self.data = data

    def odd(self) -> str:
        return self.data[1::2]

    def tail(self, n: int) -> str:
        def inner() -> str:
            return self.data[: -n - 1 : -1]

        return inner()


b = Buf("0123456789")
print(b.odd(), b.tail(3), b.data[::-2])
nested = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
print([row[::-1] for row in nested[::-1]], nested[::2][0][::2], "".join(c for c in "hello"[::-1]))
