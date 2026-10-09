# Effect summaries (IFn.fx): tools/check_ir.sh compiles this with PYSTACHY_IRFX=1, which prints
# each function's letters (FX), and compares them with effects.fx. A raw op (a load, a store or
# arithmetic, until steps 10 to 12 make them ops) has the letters its text shows: none for a
# slot's load or store, rG or wG for a global's, rO or wO for an object's field's or flag's
# (P.__init__, P.__eq__, K.get), and rL rD rO or wL wD wO through any other address (a list's or
# a dict's header).
import sys


class P:
    def __init__(self, x: int) -> None:
        self.x = x

    def __eq__(self, o: "P") -> bool:
        return self.x == o.x


class K:
    c: int = 1  # a class variable (K.c = 2 below assigns it)

    def get(self) -> int:
        return self.c  # the object's flag and field (rO), else the class's global (rG)


def band(a: int, b: int) -> int:
    return a & b  # raw ops only


def add(a: int, b: int) -> int:
    return a + b  # an overflow check: R


def first(xs: list[int]) -> int:
    return xs[0]  # list.get: R rL


def grow(xs: list[int]) -> None:
    xs.append(1)  # list.append: A rL wL


def show(s: str) -> None:
    print(s)  # write: I rF wF (and A, R)


def bump(d: dict[str, int], k: str) -> None:
    d[k] = d.get(k, 0) + 1  # dict.get, dict.set, an overflow check


def find(xs: list[P], p: P) -> int:
    return xs.index(p)  # list.index on objects: __eq__ may run, so every letter (U)


def findi(xs: list[int]) -> int:
    return xs.index(3)  # list.index on ints: no user code, but I (its ValueError's repr guards recursion)


def boom() -> None:
    raise ValueError("boom")  # raise: R (N is no summary's)


def leave() -> None:
    sys.exit(2)  # exit: R I


def ping(n: int) -> None:
    if n > 0:
        pong(n - 1)  # pong, compiled after ping, prints: ping gets I rF wF from the fixpoint


def pong(n: int) -> None:
    print(n)
    ping(n)


def both() -> int:
    return add(1, 2) + first([1])  # its callees' letters, and its own


ys = [P(1), P(2)]
xs = [1, 2, 3]
d: dict[str, int] = {}
K.c = 2
print(band(6, 3), add(1, 2), first(xs), find(ys, P(2)), findi(xs), both(), K().get())
grow(xs)
show("x")
bump(d, "a")
ping(2)
if len(xs) > 10:
    boom()
if len(xs) > 20:
    leave()
