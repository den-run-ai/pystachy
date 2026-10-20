# Variables assigned on only some paths: reads that find them assigned behave as in CPython
import sys


def pick(flag: bool) -> int:
    if flag:
        x = 1
    return x


def first_neg(xs: list[int]) -> int:
    for v in xs:
        if v < 0:
            found = v
            break
    return found


def until(xs: list[int]) -> int:
    i = 0
    while True:
        last = xs[i]
        if last > 2:
            break
        i += 1
    return last


def later() -> int:
    return COUNT


def loop_carried(n: int) -> list[int]:
    out: list[int] = []
    prev: int
    for i in range(n):
        if i > 0:
            out.append(prev)
        prev = i * i
    return out


def both(c: bool) -> str:
    if c:
        s = "a"
    else:
        s = "b"
    return s


print(pick(True), first_neg([3, -2, 5]), until([1, 2, 3, 4]), loop_carried(4), both(False))
COUNT = 5
print(later())
if len(sys.argv) > 5:
    MAYBE = 1
try_these = sys.argv[1]
print(try_these)
which = sys.argv[1]


class Lazy:
    label: str
    hits: int = 0

    def __init__(self, ready: bool):
        if ready:
            self.value = 10
        self.hits += 1

    def get(self) -> int:
        return self.value


z = Lazy(True)
z.label = "late"
print(z.get(), z.label, z.hits, Lazy(False).hits)
