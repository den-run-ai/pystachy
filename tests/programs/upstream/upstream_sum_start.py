# Adapted from CPython cbc944f4bc59639a444dd971c737788ba2283a91
# Lib/test/test_builtin.py::BuiltinTest.test_sum (PSF license: upstream/CPYTHON-LICENSE.txt).
# Remove unittest scaffolding; retain the range/start assertion and test supported typed iterables.
# Additional ordering regressions check iterator construction, start evaluation, then traversal.
from typing import Iterator

assert sum(range(10), 1000) == 1045
print(sum(range(10), 1000), sum(range(3), 0.5), sum(range(0), 7))
print(sum(reversed(range(5)), 10), sum(reversed([1, 2, 3]), 10))
print(sum((i + x for i, x in enumerate([2, 3], 4)), 10))
print(sum((x + y for x, y in zip([1, 2], [3, 4])), 10))


def number(tag: str, x: int) -> int:
    print(tag, x)
    return x


def source() -> list[int]:
    print("source")
    return [1, 2]


class Items:
    def __init__(self) -> None:
        print("construct")
        self.xs = [1, 2]

    def __iter__(self) -> Iterator[int]:
        print("iter")
        return iter(self.xs)


# Plain iterable: evaluate start before acquiring its iterator.
print(sum(Items(), number("plain start", 10)))
# Generator: evaluate outer iterable and acquire its iterator before start.
print(sum((number("body", x) for x in Items()), number("generator start", 10)))
print(sum((number("body", x) for x in source()), number("generator start", 10)))
print(sum(range(number("range stop", 3)), number("range start", 10)))
print(sum((x for _, x in enumerate(Items(), number("enumerate start", 4))), number("sum start", 10)))
print(sum((x + y for x, y in zip(Items(), Items())), number("zip start", 10)))

xs = [1, 2]


def append_start() -> int:
    print("append start")
    xs.append(10)
    return 5


# Capture the iterable, without copying it; forward iteration sees the append.
print(sum((number("body", x) for x in xs), append_start()), xs)
xs = [1, 2]
# A reverse iterator keeps its original length and ignores appended items.
print(sum(reversed(xs), append_start()), xs)
xs = [1, 2]
print(sum((number("body", x) for x in reversed(xs)), append_start()), xs)


def pop_start() -> int:
    print("pop start")
    xs.pop()
    return 5


xs = [1, 2]
# Its original last index is now past the shortened list, so reversed is exhausted.
print(sum(reversed(xs), pop_start()), xs)
x = 100
print(sum((x for x in [1, 2]), x), x)

keys = {1: 1}


def dict_start() -> int:
    print("dict start")
    keys[2] = 2
    return 5


try:
    print(sum((k for k in keys), dict_start()))
except RuntimeError as e:
    print(type(e).__name__, str(e))


def bad_start() -> int:
    print("bad start")
    raise ValueError("start")


try:
    print(sum((number("not traversed", x) for x in Items()), bad_start()))
except ValueError as e:
    print(type(e).__name__, str(e))
try:
    print(sum(range(0, 2, number("zero step", 0)), number("not evaluated", 10)))
except ValueError as e:
    print(type(e).__name__, str(e))
try:
    print(sum(reversed(range(0, 2, 0)), number("not evaluated", 10)))
except ValueError as e:
    print(type(e).__name__, str(e))


def missing_bound() -> int | None:
    print("missing bound")
    return None


def bad_bound() -> int:
    print("bad bound")
    raise ValueError("bound")


# Evaluate every range argument before checking their index types; construction still precedes start.
try:
    print(sum(range(missing_bound(), number("later bound", 3)), number("not evaluated", 10)))
except TypeError as e:
    print(type(e).__name__, str(e))
try:
    print(sum(range(missing_bound(), bad_bound()), number("not evaluated", 10)))
except ValueError as e:
    print(type(e).__name__, str(e))


def missing() -> list[int] | None:
    print("missing")
    return None


try:
    print(sum((x for _, x in enumerate(missing())), number("not evaluated", 10)))
except TypeError as e:
    print(type(e).__name__, str(e))
try:
    print(sum((number("not traversed", x) for x in missing()), number("not evaluated", 10)))
except TypeError as e:
    print(type(e).__name__, str(e))
print(sum([number("eager", x) for x in source()], number("eager start", 10)))

# An explicit conversion requests the supported numeric result on empty and nonempty inputs.
empty: list[int] = []
print(sum(empty, int(False)), sum(empty, int(True)), sum([1, 2], int(True)))
