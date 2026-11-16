# Runtime-length tuples as dict keys (#1460): hashed and compared by their items and length, as
# CPython's tuples are, so that a key built one way finds an equal one built another, whatever its
# length, the empty tuple too; items are ints, bools, strs or str | None


Kind = tuple[bool, ...]


class Cache:
    def __init__(self) -> None:
        self.seen: dict[Kind, set[str]] = {}

    def add(self, kind: Kind, name: str) -> None:
        self.seen.setdefault(kind, set()).add(name)


def ints(n: int) -> tuple[int, ...]:
    return tuple(range(n))


def strs(xs: list[str]) -> tuple[str, ...]:
    return tuple(xs)


def maybe(xs: list[str | None]) -> tuple[str | None, ...]:
    return tuple(xs)


c = Cache()
k: Kind = (True, False)
c.add(k, "a")
c.add((True, False), "b")
c.add(tuple([True, False]), "c")
c.add((), "e")
c.add((True,), "t")
for key in sorted(c.seen):
    print(key, sorted(c.seen[key]))
print((True, False) in c.seen, (False,) in c.seen, len(c.seen))

d: dict[tuple[int, ...], str] = {}
for n in range(5):
    d[ints(n)] = "n" + str(n)
d[(0, 1)] = "fixed"
print(len(d), d[()], d[(0,)], d.get((0, 1, 2)), d.get((9,)), (0, 1, 2, 3) in d, (1,) in d)
print(sorted(d.items()))
t = ints(4)
print(d[t[:2]], d[t[:0]], d[t[1:1]], d[t[:3] + t[3:]], d[(True, 1)] if (True, 1) in d else "-", (False,) in d)
del d[(0, 1, 2)]
print(d.pop((0,)), d.pop((5, 5), "none"), len(d), sorted(d))
print(d[(False, True)], d.get((True,), "-"), d.pop((False, True, 2, True), "-"))
try:
    print(d[(True, 5)])
except KeyError as e:
    print("KeyError", e)

s: dict[tuple[str, ...], int] = {}
s[strs(["a", "b"])] = 1
s[("a", "b")] = 2
s[strs([])] = 3
s[strs(["b" * 3, "a"])] = 4
print(sorted(s.items()), s[("bbb", "a")], s[()])

o: dict[tuple[str | None, ...], int] = {maybe([None]): 1, maybe(["x", None]): 2}
o[(None,)] = 5
print(sorted(o.values()), o[("x", None)], (None, None) in o, o.get(maybe([])))
print({k: v for k, v in o.items() if v > 2})
print(hash(ints(3)) == hash((0, 1, 2)), hash(()) == hash(ints(0)), hash(strs(["a"])) == hash(("a",)))
