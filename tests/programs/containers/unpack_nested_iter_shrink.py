# Unpacking a list into nested tuple targets: CPython reads every item before the first
# store, so an item whose __iter__ (or __next__) shortens or regrows the list does not
# change which items the later targets take.
from typing import Iterator


class P:
    def __init__(self, owner: list["P"], a: int) -> None:
        self.owner = owner
        self.a = a

    def __iter__(self) -> Iterator[int]:
        self.owner.clear()
        return iter([self.a, -self.a])


class Regrow:
    def __init__(self, owner: list["Regrow"], a: int) -> None:
        self.owner = owner
        self.a = a

    def __iter__(self) -> Iterator[int]:
        self.owner.clear()
        self.owner.append(Regrow(self.owner, 100))
        return iter([self.a, self.a * 10])


class Popper:
    def __init__(self, owner: list["Popper"], a: int) -> None:
        self.owner = owner
        self.a = a
        self.n = 0

    def __iter__(self) -> "Popper":
        return self

    def __next__(self) -> int:
        if len(self.owner) > 0:
            self.owner.pop()
        self.n += 1
        if self.n > 2:
            raise StopIteration
        return self.a * self.n


def plain() -> None:
    xs: list[P] = []
    xs.append(P(xs, 1))
    xs.append(P(xs, 2))
    (a, b), (c, d) = xs
    print(a, b, c, d, len(xs))


def regrow() -> None:
    xs: list[Regrow] = []
    for i in range(12):
        xs.append(Regrow(xs, i + 1))
    (a, b), (c, d), (e, f), (g, h), (i2, j), (k, m), (n, o), (p, q), (r, s), (t, u), (v, w), (y, z) = xs
    print(a, b, c, d, e, f, g, h, i2, j, k, m, n, o, p, q, r, s, t, u, v, w, y, z, len(xs))


def loop() -> None:
    rows: list[list[P]] = []
    for i in range(3):
        row: list[P] = []
        row.append(P(row, i))
        row.append(P(row, i + 10))
        rows.append(row)
    for (a, b), (c, d) in rows:
        print(a, b, c, d)


def popper() -> None:
    xs: list[Popper] = []
    for i in range(3):
        xs.append(Popper(xs, i + 1))
    (a, b), (c, d), (e, f) = xs
    print(a, b, c, d, e, f, len(xs))


def flat() -> None:
    xs = [1, 2, 3]
    a, b, c = xs
    print(a, b, c)
    ys = [[4, 5], [6, 7]]
    (d, e), (f, g) = ys
    print(d, e, f, g)


plain()
regrow()
loop()
popper()
flat()
