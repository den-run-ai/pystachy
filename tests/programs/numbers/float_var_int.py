# Variables annotated float that are given ints (#1534): a module variable, also assigned in a
# function, a local, a local that a closure assigns and a generator's local. Each holds an
# int | float, as if annotated so, and the int stays an int, as in CPython.
from collections.abc import Iterator

y: float = 3
total: float = 0
count: float = 0.0
later: float
later = 4


def add(v: float) -> None:
    global total, count
    total += v
    count = count + 1


def reset() -> None:
    global total, count
    total = 0
    count = 0


def locals_(n: int) -> str:
    a: float = n
    b: float
    b = n * 2
    c: float = 1.5
    c = n
    d: float = True
    out = f"{a} {b} {c} {d} {isinstance(a, int)} {isinstance(d, bool)}"
    a += 0.5
    b, c = c, 2.5
    for d in [1.5, 2.5]:
        pass
    return out + f" | {a} {b} {c} {d}"


def closure() -> str:
    acc: float = 0

    def bump(v: float) -> None:
        nonlocal acc
        acc += v

    def zero() -> None:
        nonlocal acc
        acc = 0

    bump(1.5)
    first = acc
    zero()
    cleared = acc
    bump(2.0)
    return f"{first} {cleared} {acc} {isinstance(cleared, int)}"


def running(n: int) -> Iterator[str]:
    t: float = 0
    for i in range(n):
        yield f"{t}"
        t += i / 2
    t = n
    yield f"{t}"


print(y, y / 2, y + 1, isinstance(y, int), later, later * 1.5)
y = 2.5
later = 0.5
print(y, y / 2, isinstance(y, int), later)
add(2.5)
print(total, count, isinstance(total, int), isinstance(count, int))
add(3.5)
print(total, count, total / 2)
reset()
print(total, count, isinstance(total, int), isinstance(count, int))
print(locals_(3))
print(locals_(0))
print(closure())
print(list(running(3)))
