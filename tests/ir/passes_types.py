# The IR passes over what the typed IR adds (tools/check_ir.sh compiles this with every pass on and
# compares the runtime calls of each function with passes_types.calls): a tuple key, an optional
# dict, a NamedTuple's field and a boxed number are values like any other, and the container
# protocol's dunders are calls, whose summaries say whether a dict lookup still holds after them.
from typing import Iterator, NamedTuple, Optional


class Bag:
    def __init__(self, d: dict[str, int]) -> None:
        self.d = d

    def __contains__(self, k: str) -> bool:
        return k in self.d  # reads a dict, writes none


class Drop:
    def __init__(self, d: dict[str, int]) -> None:
        self.d = d

    def __contains__(self, k: str) -> bool:
        return self.d.pop(k, 0) > 0  # writes a dict (wD)


class E:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, o: "E") -> bool:
        return self.n == o.n


class Seq:
    def __init__(self, xs: list[int]) -> None:
        self.xs = xs

    def __iter__(self) -> Iterator[int]:
        return iter(self.xs)


class P(NamedTuple):
    d: dict[str, int]
    xs: list[int]


class Pt(NamedTuple):
    a: int
    b: int


def tkey(d: dict[tuple[int, str], int], t: tuple[int, str]) -> None:
    if t in d:
        d[t] += 1  # find, val, entry_set


def tbuilt(d: dict[tuple[int, str], int], a: int) -> None:
    if (a, "x") in d:
        d[a, "x"] += 1  # another tuple: has; then entry, val, entry_set


def optd(d: Optional[dict[str, int]], k: str) -> None:
    if d is not None:
        if k in d:
            d[k] += 1  # find, val, entry_set


def optand(d: Optional[dict[str, int]], k: str) -> None:
    if d is not None and k in d:
        d[k] += 1  # the test is the and's phi, which dictfuse does not read: has; entry, val, entry_set


def ntfield(p: P, k: str) -> None:
    if k in p.d:
        p.d[k] += 1  # the field's loads are one value: find, val, entry_set


def boxv(d: dict[str, Optional[int]], k: str) -> int:
    if k in d:
        v = d[k]  # find, val
        if v is not None:
            return v
    return 0


def dunder(d: dict[str, int], b: Bag, k: str) -> None:
    if k in d:
        if k in b:  # Bag.__contains__ writes no dict: find, (call), val, entry_set
            d[k] += 1


def dunder_w(d: dict[str, int], b: Drop, k: str) -> None:
    if k in d:
        if k in b:  # Drop.__contains__ pops: has, (call), entry, val, entry_set
            d[k] += 1


def objeq(d: dict[str, int], es: list[E], e: E, k: str) -> None:
    if k in d:
        if e in es:  # list.find of objects may run any __eq__ (U): has, then entry, val, entry_set
            d[k] += 1


def objloop(s: Seq) -> int:
    t = 0
    for x in s:  # the list __iter__ returns: an inline load
        t += x
    return t


def optloop(xs: Optional[list[int]]) -> int:
    t = 0
    if xs is not None:
        for x in xs:  # an inline load
            t += x
    return t


def ntloop(p: Pt) -> int:
    t = 0
    for v in p:  # the list of its items: an inline load
        t += v
    return t


td: dict[tuple[int, str], int] = {(1, "x"): 1}
tkey(td, (1, "x"))
tbuilt(td, 1)
sd = {"a": 1}
optd(sd, "a")
optand(sd, "a")
ntfield(P(sd, [1]), "a")
print(boxv({"a": None, "b": 2}, "b"))
dunder(sd, Bag(sd), "a")
dunder_w(sd, Drop({"a": 1}), "a")
objeq(sd, [E(1)], E(1), "a")
print(td, sd, objloop(Seq([1, 2])), optloop([3]), ntloop(Pt(4, 5)))
