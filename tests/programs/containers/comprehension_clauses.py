# Comprehensions with several for and if clauses: list, set and dict comprehensions and
# generator expressions given to their consumers. The first iterable is evaluated once, in the
# scope around the comprehension; each later iterable and condition at its turn, for each item
# of the clauses before it; the variables are the comprehension's own
import math
import os
from typing import Generic, TypeVar

T = TypeVar("T")


def seq(tag: str, n: int) -> list[int]:
    print("iter", tag, n)
    return list(range(n))


def test(tag: str, b: bool) -> bool:
    print("test", tag, b)
    return b


def shapes() -> None:
    xs = [1, 2, 3]
    ys = [10, 20]
    print([x * y for x in xs for y in ys if x != 2])
    print([(a, b) for a in xs if a > 1 for b in ys if b // 10 != a])
    print([x for x in [0, 1, 2, 3] if x if x != 2])
    print(sorted({(i, j) for i in range(3) for j in range(i)}))
    print({k: v for row in [[("a", 1), ("b", 2)], [("a", 3)]] for k, v in row})
    print([(i, j, k) for i in range(2) for j in range(i, 3) if j for k in "ab" if k != "b" or i])
    print([c for w in ["ab", "", "cd"] for c in w])
    print([(i, w) for i, ws in enumerate([["héllo"], [], ["wörld", "!"]]) for w in ws])
    print([n for k, v in {"a": 2, "b": 0, "c": 1}.items() for n in range(v)])
    print([p for a, b in zip("ab", "xy") for p in (a, b)])
    print([x for x in reversed([1, 2]) for _ in range(x)])
    print([[x for x in row if x % 2] for row in [[1, 2, 3], [4, 5]] for _ in range(2)])
    print([y for x in [[1, 2], [3]] for y in [z * 10 for z in x]])
    print({w: [c for c in w if c != "a"] for ws in [["ab", "ca"], ["b"]] for w in ws})
    print([x for x in [[1, 2], [3]] for x in x])


def order() -> None:
    print([(a, b) for a in seq("outer", 3) if test("a", a != 1) for b in seq("inner", a) if test("b", b == 0)])
    print({note: b for note in ["x"] for b in seq(note, 2)})


def scope() -> None:
    x = "outer x"
    y = -1
    print([x for x in "ab" for y in "cd"], x, y)
    rows = [[1, 2], [3]]
    print([rows for rows in rows for rows in rows], rows)
    i = 7
    print(sum(i * j for i in range(3) for j in range(i)), i)


def early() -> None:
    seen: list[int] = []

    def look(v: int) -> int:
        seen.append(v)
        return v

    grid = [[1, 2], [3, 4], [5]]
    print(any(look(x) > 2 for row in grid for x in row), seen)
    seen.clear()
    print(all(look(x) < 2 for row in grid for x in row), seen)
    seen.clear()
    print(any(look(x) > 9 for row in grid for x in row), all(look(x) < 9 for row in grid for x in row), seen)
    print(any(x for row in [[0], []] for x in row), all(x for row in [[1], []] for x in row))
    print(any(x == 4 for row in grid if len(row) > 1 for x in row if x % 2 == 0 for _ in range(2)))


def consumers() -> None:
    grid = [[3, 1], [], [2, 5, 4]]
    print(sum(x for row in grid for x in row), sum((x for row in grid for x in row), 10))
    print(min(x for row in grid for x in row), max(x for row in grid for x in row if x < 5))
    print(min((x for row in grid for x in row), key=lambda v: -v), max((x for row in grid for x in row), key=lambda v: v % 3))
    print(sorted(x for row in grid for x in row), sorted((x for row in grid for x in row), reverse=True))
    print(sorted((x for row in grid for x in row), key=lambda v: v % 3))
    print(list(x for row in grid for x in row), tuple(x for row in grid for x in row), tuple(str(x) for x in range(2)))
    print(sorted(set(x % 3 for row in grid for x in row)), sorted(frozenset(x for row in grid for x in row)))
    print("-".join(str(x) for row in grid for x in row), "".join(c.upper() for w in ["ab", "c"] for c in w))
    print(math.fsum(x / 2 for row in grid for x in row), math.prod(x for row in grid for x in row))
    ys: list[int] = [0]
    ys.extend(x for row in grid for x in row if x > 2)
    print(ys)
    s = {0}
    s.update(x for row in grid for x in row)
    print(sorted(s))
    s.difference_update(x for row in grid for x in row if x % 2)
    print(sorted(s), sorted(s.union(x * 10 for row in grid for x in row)))
    print(tuple(range(3)), tuple(reversed(ys)), tuple(map(str, ys)), tuple(filter(None, [0, 2])))


def rebinding() -> None:
    # a later for clause that binds an earlier clause's variable binds the same variable: once the
    # loop between them has run, the clauses between them read the later clause's value
    print([x for x in ["ab"] for _ in range(2) for x in x])
    print([1 for x in "ab" for _ in range(2) if x == "a" for x in "zz"])
    print([b for b in [3] for a in range(2) for b in range(b)])
    print({x: n for x in ["ab"] for n in range(2) for x in x}, sorted({x for x in ["ab"] for n in range(3) for x in x}))
    print(sum(1 for x in ["ab"] for _ in range(2) for x in x), tuple(x for x in ["ab"] for _ in range(2) for x in x))
    print(any(x == "b" for x in ["ab"] for _ in range(2) if x != "a" for x in x), all(x != "b" for x in ["ab"] for _ in range(2) for x in x))
    print([x for x in ["abc"] for _ in range(2) for x in x for _ in range(2) for x in x + x])
    print([(x, y) for x in [1, 2] for y in [10, 20] for x in [x + y]])
    d: dict[str, int] = {}
    print([0 for x in ["a", "b"] for d[x] in [1, 2] for x in ["z"]], d)
    e: dict[str, int] = {}
    print([x for x in "ab" for e[x], x in [(1, "p"), (2, "q")]], e)
    f: dict[str, int] = {}
    print([x for x in "ab" for x, f[x] in [("p", 1), ("q", 2)]], f)
    xs: list[int | None] = [None, 1]
    ys: list[int | None] = [None]
    try:
        print([x for x in xs if x is not None for _ in range(2) if x + 1 > 0 for x in ys])
    except TypeError as exc:
        print("TypeError", exc)


def mutation() -> None:
    xs = [1, 2]
    print([y for _ in [0] for y in xs if len(xs) < 5 and xs.append(y) is None], xs)
    d = {"a": 1, "b": 2}
    try:
        print([k for _ in [0] for k in d if d.pop(k)])
    except RuntimeError as e:
        print("RuntimeError", e)
    try:
        print([row[2] for row in [[1, 2, 3], [4]] for _ in range(2)])
    except IndexError as e:
        print("IndexError", e)


def products(*args: int) -> list[int]:
    return [a * b for a in args for b in args if a <= b]


def cells(n: int) -> list[int]:
    count = 0

    def bump() -> int:
        nonlocal count
        count += 1
        return count

    def grid() -> list[int]:
        return [i * 10 + j + bump() * 100 for i in range(n) for j in range(n) if i < j]

    return grid() + [count]


def files() -> None:
    p = "comprehension_clauses_" + str(os.getpid()) + ".txt"
    with open(p, "w") as w:
        w.write("one\ntwo\nthree\n")
    print([line.strip() for k in range(2) for line in open(p) if k or line.startswith("t")])
    print(any(line.startswith("tw") for _ in range(3) for line in open(p)))
    print(all(not line.startswith("x") for _ in range(2) for line in open(p)))
    os.remove(p)


class Grid:
    def __init__(self, rows: list[list[int]]) -> None:
        self.rows = rows

    def cells(self) -> list[tuple[int, int, int]]:
        return [(i, j, v) for i, row in enumerate(self.rows) for j, v in enumerate(row) if v != 0]

    def where(self) -> dict[int, tuple[int, int]]:
        return {v: (i, j) for i, row in enumerate(self.rows) for j, v in enumerate(row)}

    def total(self) -> int:
        return sum(v for row in self.rows for v in row)


class Box(Generic[T]):
    def __init__(self, items: list[list[T]]) -> None:
        self.items = items

    def flat(self) -> list[T]:
        return [x for xs in self.items for x in xs]

    def distinct(self) -> set[T]:
        return {x for xs in self.items for x in xs}


def pairs(xs: list[T], ys: list[T]) -> list[tuple[T, T]]:
    return [(x, y) for x in xs for y in ys if x != y]


def flat(rows):
    return [x for row in rows for x in row]


shapes()
order()
scope()
early()
consumers()
rebinding()
mutation()
print(products(1, 2, 3), products(), cells(3))
files()
g = Grid([[1, 0], [0, 2], [3, 4]])
print(g.cells(), g.where(), g.total())
print(Box([[1, 2], [3, 1]]).flat(), sorted(Box([[1, 2], [3, 1]]).distinct()), Box([["a"], ["b", "c"]]).flat())
print(pairs([1, 2], [2, 3]), pairs(["a"], ["a", "b"]))
print(flat([[1, 2], [3]]), flat([["a"], ["b"]]))
table = [[r * c for c in range(1, 4)] for r in range(1, 3)]
print(table, [v for row in table for v in row if v % 2 == 0], {v % 4 for row in table for v in row})
print(max(len(w) for line in ["a bc", "def g"] for w in line.split()))
y = "global y"
x = 5
print([(x, y) for x in range(3) for y in range(x)], x, y)
print({y: x for x in range(2) for y in "ab"}, x, y)
print([x for x in [7] for _ in range(2) for x in range(x - 5)], x)
