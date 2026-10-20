# fields typed by a tuple display, a dict display, a list of tuples, a list repeated, list() of a
# range or a list and sorted() of a list, and an __init__ whose first parameter is not named self
from typing import Iterator


class C:
    def __init__(self, n: int) -> None:
        self.t = (1, "a", 2.5)
        self.d = {"a": [1], "b": [2, 3]}
        self.ps = [(1, "a"), (2, "b")]
        self.rep = [n] * n
        self.srep = "ab" * n
        self.r = list(range(n))
        self.c = list(self.rep)
        self.s = sorted([3, 1, 2])
        self.k = {(1, "x"): True}

    def __iter__(self) -> Iterator[int]:
        return iter(self.r)


class P:
    def __init__(this, v: int) -> None:
        this.v = v
        this.w = (v, v)

    def get(this) -> int:
        return this.v + this.w[1]


c = C(3)
print(c.t, c.d, c.ps, c.rep, c.srep, c.r, c.c, c.s, c.k, list(c), sum(c))
c.t = (2, "b", 0.5)
c.d["c"] = []
print(c.t, c.d, P(4).get())
