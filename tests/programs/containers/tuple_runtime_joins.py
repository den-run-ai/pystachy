# Tuples of other lengths join into a runtime-length tuple of their items' join: a function's
# returns, a local a loop rebinds, the arms of a conditional expression, a display's items
# and a dict display's values ((), (n,) and (n, n): tuple[int, ...])
import sys


class Base:
    def __init__(self, n: int) -> None:
        self.n = n

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.n})"


class Derived(Base):
    pass


def pick(n: int):
    if n > 1:
        return (n, n)
    if n == 1:
        return (n,)
    return ()


def grow(n: int):
    acc = ()
    for i in range(n):
        acc = acc + (i,)
    return acc


flag = len(sys.argv) > 5
print(pick(2), pick(1), pick(0))
print(grow(3), grow(0))
objs = (Base(1),) if flag else (Base(2), Base(3))
print(objs, len(objs))
mixed = (Derived(1),) if flag else (Base(2), Base(3))
print(mixed)
table = {"none": (), "one": (1,), "two": (1, 2)}
print(table, sorted(len(v) for v in table.values()))
for x in (1,) if flag else (4, 5):
    print(x)
a, b = pick(2)
print(a + b)
try:
    c, d = pick(1)
except ValueError as e:
    print("ValueError:", e)
