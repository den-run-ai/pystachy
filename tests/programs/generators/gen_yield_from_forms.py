# yield from the iterables a for loop takes as calls (#490): range(), reversed(), enumerate(),
# zip(), map() and filter(), and generator expressions with several for and if clauses, inline
# (whose later clauses' variables are the expression's own) and as values; the value of yield
# from an iterable (None); and `return v` before an unreachable yield, the idiom of an empty
# generator that returns a value.
from collections.abc import Generator, Iterator


def forms() -> Iterator[int]:
    yield from range(3)
    yield from range(10, 4, -2)
    yield from reversed([7, 8])
    yield from map(len, ["a", "bb"])
    yield from filter(None, [0, 5, 0, 6])
    yield from (a * b for a in range(1, 3) for b in range(2) if a != b)


def pairs() -> Iterator[tuple[int, str]]:
    yield from enumerate("xy")
    yield from zip([5, 6], "pq")


b = 99


def shadow() -> Iterator[int]:
    a = "kept"
    yield from (a * 2 for a in range(2) for b in range(2))
    print(a, b)


def made(n: int) -> Iterator[str]:
    return (str(i) + s for i in range(n) for s in ["a", "b"] if i != 1)


def none_value() -> Iterator[int]:
    x = yield from range(2)
    print("value", x)


def empty() -> Generator[int, None, int]:
    return 5
    yield 0


def nothing() -> Iterator[int]:
    return
    yield -1


def delegate() -> Generator[int, None, None]:
    v = yield from empty()
    print("empty() returned", v)
    yield v
    yield from nothing()


print(list(forms()))
print(list(pairs()))
print(list(shadow()))
print(list((a, c) for a in range(2) for c in "xy"))
print(list(a + c for a in range(3) if a for c in range(a) if c != 1))
print(list(made(3)))
print(list(none_value()))
print(list(delegate()), list(nothing()))
