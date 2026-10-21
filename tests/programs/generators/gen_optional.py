# A generator or None (#490): Generator[Y, None, None] | None in variables, fields and lists, as
# a lazily made generator is often kept; None is the null handle, and the consumers raise
# CPython's TypeError for it.
from collections.abc import Generator, Iterator


def count(n: int) -> Iterator[int]:
    for i in range(n):
        yield i


cur: Generator[int, None, None] | None = None
for k in range(3):
    if cur is None:
        cur = count(2)
    v = next(cur, -1)
    print(k, v)
    if v < 0:
        cur = None


class Holder:
    def __init__(self) -> None:
        self.gen: Generator[int, None, None] | None = None

    def step(self) -> int:
        if self.gen is None:
            self.gen = count(3)
        return next(self.gen, -1)


h = Holder()
print([h.step() for _ in range(5)])
gs: list[Generator[int, None, None] | None] = [count(2), None]
for q in gs:
    print(q is None, next(q) if q is not None else -5)
maybe: Generator[int, None, None] | None = count(1)
if maybe:
    print("truthy", list(maybe))
none: Generator[int, None, None] | None = None
try:
    for x in none:
        print(x)
except TypeError as e:
    print("TypeError:", e)
try:
    print(next(none))
except TypeError as e:
    print("TypeError:", e)
try:
    print(sum(none))
except TypeError as e:
    print("TypeError:", e)
try:
    print(list(none))
except TypeError as e:
    print("TypeError:", e)
try:
    print(3 in none)
except TypeError as e:
    print("TypeError:", e)
