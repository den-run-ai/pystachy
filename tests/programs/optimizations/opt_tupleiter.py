# for loops over tuples of one item type, which step through the tuple's slots (tupleiter: no list
# of its items). The loop goes through the tuple evaluated once, before it, whatever its body
# rebinds; break, continue and else; nested tuples and unpacking; enumerate(), zip() and
# reversed(); items of every kind; exceptions; a body that allocates while the tuple it steps
# through is no variable's any more. Run with PYSTACHY_OPT=-tupleiter too.
from typing import NamedTuple


class P:
    def __init__(self, v: int) -> None:
        self.v = v


class Pt(NamedTuple):
    x: int
    y: int
    z: int


class Grid:
    def __init__(self) -> None:
        self.offs = (1, 2, 3)

    def walk(self) -> int:
        s = 0
        for d in self.offs:
            self.offs = (100, 200, 300)  # (the loop goes on over the tuple it started with)
            s += d
        return s


NB = ((0, 1), (1, 0), (0, -1), (-1, 0))
calls = 0


def rebind() -> None:
    global NB
    NB = ((5, 5), (6, 6), (7, 7), (8, 8))


def make() -> tuple[int, int, int]:
    global calls
    calls += 1
    return (calls, calls * 10, calls * 100)


def first_neg(t: tuple[int, int, int]) -> int:
    for x in t:
        if x < 0:
            raise ValueError(f"negative: {x}")
    return 0


def find(t: tuple[str, str, str], w: str) -> int:
    i = 0
    try:
        for s in t:
            if s == w:
                return i
            i += 1
    finally:
        print("finally", i)
    return -1


def maybe(n: int) -> tuple[int, int] | None:
    return (n, n + 1) if n > 0 else None


def churn(n: int) -> int:
    # each round rebinds t, so only the loop holds the tuple it steps through while str()
    # allocates: a collection must keep it (and its items)
    t = ("a", "bb", "ccc")
    acc = 0
    for k in range(n):
        for s in t:
            t = (s[:1] + str(k % 7), s + "!", str(k))
            acc += len(s) + len(str(k * 31))
    return acc + len(t[0])


def rebinding() -> None:
    t = (1, 2, 3)
    for x in t:
        t = (x * 10, 20, 30)
        print(x, t)
    print(t)
    for dx, dy in NB:
        rebind()
        print(dx, dy, end="; ")
    print(NB[0])
    print(Grid().walk())
    for x in make():
        print(x, end=" ")
    print("calls", calls)


def flow() -> None:
    for x in (1, 2, 3, 4, 5):
        if x == 2:
            continue
        if x == 4:
            break
        print("item", x)
    else:
        print("no break")
    for x in (6, 7):
        pass
    else:
        print("else after", x)
    t3 = (1, 2, 3)
    pairs = 0
    for a in t3:
        for b in t3:
            if a < b:
                pairs += 1
    print("pairs", pairs)
    n = 0
    for x in (1, 2, 3):
        n += 1
        if n > 10:
            break
    else:
        print("ran", n)
    for pair in (("a", "b"), ("c", "d"), ("e", "f")):
        for w in pair:
            if w == "c":
                break
            print(w, end=" ")
        else:
            print("|", end=" ")
            continue
        print("broke", end=" ")
    print()


def kinds() -> None:
    for (a, b), c in (((1, 2), 3), ((4, 5), 6)):
        print(a, b, c)
    for row in ((1, 2, 3), (4, 5, 6)):
        for v in row:
            print(v, end=" ")
    print()
    for f in (0.5, -1.25, 2.0):
        print(f * 2, end=" ")
    print()
    for flag in (True, False):
        print(flag, not flag, end=" ")
    print()
    for s in ("a", "bc"):
        print(s.upper(), len(s), end=" ")
    print()
    opts: tuple[str | None, str | None] = ("x", None)
    for o in opts:
        print(o is None, o, end=" ")
    print()
    nums: tuple[int | None, int | None, int | None] = (None, 3, -4)
    for m in nums:
        print(m, m is not None and m > 0, end=" ")
    print()
    for p in (P(1), P(2)):
        p.v += 10
        print(p.v, end=" ")
    print()
    for l in ([1], [2, 3]):
        l.append(0)
        print(l, end=" ")
    print()
    for d in ({"a": 1}, {"b": 2}):
        print(d, end=" ")
    print()
    for c in Pt(3, 4, 5):
        print(c, end=" ")
    print()
    nine = (1, 2, 3, 4, 5, 6, 7, 8, 9)
    print(sum([x for x in nine]), [x * x for x in nine if x % 2 == 0])
    print(sum(x for x in (1.5, 2.5)), any(x > 2 for x in (1, 2, 3)), all(x > 1 for x in (1, 2, 3)))
    for pair in [(1, 2), (3, 4)]:
        for x in pair:
            print(x, end=" ")
    print()
    last = 0
    for last in (4, 5, 6):
        pass
    print("last", last + 1)


def zipped() -> None:
    for i, x in enumerate((7, 8, 9), 1):
        print(i, x, end="; ")
    print()
    for i, s in enumerate(("p", "q")):
        print(i, s, end="; ")
    print()
    for x, y in zip((1, 2, 3), [4, 5]):
        print(x, y, end="; ")
    print()
    for x, y in zip([1, 2, 3], (4, 5)):
        print(x, y, end="; ")
    print()
    for x, s in zip((1, 2), ("a", "b")):
        print(x, s, end="; ")
    print()
    for x, y in zip((1, 2), (4, 5, 6)):
        print(x, y, end="; ")
    print()
    for x in reversed((1, 2, 3)):
        print(x, end=" ")
    print()
    for c in reversed(Pt(1, 2, 3)):
        print(c, end=" ")
    for i, c in enumerate(Pt(4, 5, 6)):
        print(i, c, end="; ")
    print()
    for s in reversed(("only",)):
        print(s)
    xs = [1, 2, 3, 4]
    for a, b in zip((10, 20, 30, 40), xs):
        xs.pop()  # (the list is read after its own test of its current length)
        print(a, b, end="; ")
    print(xs)
    ys = [1, 2]
    for a, b in zip((10, 20, 30, 40), ys):
        ys.append(a)
        print(a, b, end="; ")
    print(ys)


def errors() -> None:
    try:
        first_neg((1, -2, 3))
    except ValueError as e:
        print("caught", e)
    print(first_neg((1, 2, 3)))
    print(find(("a", "b", "c"), "b"), find(("a", "b", "c"), "z"))
    try:
        for x in maybe(0):
            print(x)
    except TypeError as e:
        print("TypeError:", e)
    for x in maybe(3):
        print(x, end=" ")
    print()
    total = 0
    for x in (1, 0, 2):
        try:
            total += 10 // x
        except ZeroDivisionError:
            print("skip", x)
            continue
    print("total", total)


rebinding()
flow()
kinds()
zipped()
errors()
print(churn(3000))
