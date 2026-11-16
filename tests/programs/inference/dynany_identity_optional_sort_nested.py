# pystachy: dynamic-any
# Sorts of optional numbers inside other sorts (#1502): a comparison that sorts such a list and
# catches its error, a raise that leaves __lt__ through the outer sort, key= that is None at run
# time, and failures deep in a merge leave every list in CPython's order and state.
from typing import Callable, Optional


class Holder:
    def __init__(self, v: int, inner: list[int | None]) -> None:
        self.v = v
        self.inner = inner

    def __lt__(self, other: "Holder") -> bool:
        try:
            self.inner.sort()
        except TypeError as e:
            print("inner", e, self.inner)
        return self.v < other.v


class Raiser:
    def __init__(self, v: int, inner: list[int | None]) -> None:
        self.v = v
        self.inner = inner

    def __lt__(self, other: "Raiser") -> bool:
        self.inner.sort(reverse=True)
        return self.v < other.v

    def __repr__(self) -> str:
        return f"Raiser({self.v}, {self.inner})"


def nested() -> None:
    shared: list[int | None] = [5, 0, None, 2, 9]
    ok: list[int | None] = [8, 1, 4]
    hs = [Holder(3, shared), Holder(1, ok), Holder(2, [7, 6]), Holder(0, [None, None])]
    hs.sort()
    print("nested", [h.v for h in hs], shared, ok)


def through() -> None:
    rs = [Raiser(5, [1, 2]), Raiser(4, [3, 1, 2]), Raiser(3, [9, 8]), Raiser(2, [7, None, 8, 1]), Raiser(1, [0])]
    try:
        rs.sort()
    except TypeError as e:
        print("through", e)
    print(rs)


def keyed(xs: list[int | None], f: Optional[Callable[[int | None], int]], rev: bool) -> None:
    try:
        xs.sort(key=f, reverse=rev)
    except TypeError as e:
        print("keyed", e)
    print("keyed after", xs)


def neg(v: int | None) -> int:
    return 0 if v is None else -v


def merged_failure(n: int, at: int, rev: bool) -> None:
    xs: list[int | None] = []
    v = 11
    for i in range(n):
        v = (v * 1103515245 + 12345) % 2147483648
        xs.append(None if i == at else v % 50)
    try:
        xs.sort(reverse=rev)
    except TypeError as e:
        print("merged", e)
    total = 0
    for i, x in enumerate(xs):
        if x is not None:
            total += (i + 1) * x
    print("merged after", len(xs), xs.index(None), total)


nested()
through()
keyed([3, 1, 2], None, False)
keyed([3, None, 1, 2], None, True)
keyed([3, None, 1, 2], neg, True)
merged_failure(200, 180, False)
merged_failure(200, 120, True)
merged_failure(300, 299, False)
