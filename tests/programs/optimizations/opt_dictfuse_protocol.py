# dictfuse (docs/typed-ir.md 7.1) must look a key up again after code that may change the dict:
# here a dunder of the class protocol (==, <, repr, len, bool, in, [], iter) moves every entry of
# the dict between a test of a key and its update, called directly or by the runtime (in, index,
# count, sorted, min, remove of a list of objects, a NamedTuple's or a tuple's ==, a dict's ==).
# Run with PYSTACHY_OPT=-dictfuse too.
from typing import Iterator, NamedTuple, Optional

G: dict[str, int] = {}


def churn(d: dict[str, int]) -> None:
    # move every entry: delete "a", insert many keys (a rebuild), put "a" back last
    v = d.pop("a", 0)
    for i in range(50):
        d[f"k{i}"] = i
    for i in range(50):
        del d[f"k{i}"]
    d["a"] = v + 1000


class M:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other: "M") -> bool:
        churn(G)
        return self.n == other.n

    def __lt__(self, other: "M") -> bool:
        churn(G)
        return self.n < other.n

    def __repr__(self) -> str:
        churn(G)
        return f"M({self.n})"

    def __len__(self) -> int:
        churn(G)
        return self.n

    def __bool__(self) -> bool:
        churn(G)
        return self.n > 0

    def __contains__(self, k: int) -> bool:
        churn(G)
        return k == self.n

    def __getitem__(self, k: int) -> int:
        churn(G)
        return k + self.n

    def __iter__(self) -> Iterator[int]:
        churn(G)
        return iter([self.n])


class P(NamedTuple):
    a: M
    b: int


def reset() -> None:
    G.clear()
    G["a"] = 1
    G["b"] = 2


def show(tag: str) -> None:
    print(tag, G["a"], list(G.keys()))


ms = [M(1), M(2), M(3)]
reset()
if "a" in G:
    u1 = M(2) in ms
    G["a"] += 1
show("in list")
reset()
if "a" in G:
    u2 = ms.index(M(2))
    G["a"] = G["a"] + 1
show("index")
reset()
if "a" in G:
    u3 = ms.count(M(3))
    G["a"] += 1
show("count")
reset()
if "a" in G:
    u0 = sorted(ms)
    G["a"] += 1
show("sorted")
reset()
if "a" in G:
    u4 = min(ms)
    G["a"] += 1
show("min")
reset()
if "a" in G:
    u5 = repr(ms[0])
    G["a"] += 1
show("repr")
reset()
if "a" in G:
    u6 = f"{ms[0]}"
    G["a"] += 1
show("fstring")
reset()
if "a" in G:
    u7 = "%s" % ms[0]
    G["a"] += 1
show("percent")
reset()
if "a" in G:
    print(ms[0])
    G["a"] += 1
show("print")
reset()
if "a" in G:
    u8 = len(ms[1])
    G["a"] += 1
show("len")
reset()
if "a" in G:
    if ms[1]:
        G["a"] += 1
show("bool")
reset()
if "a" in G:
    u9 = 2 in ms[1]
    G["a"] += 1
show("contains")
reset()
if "a" in G:
    u10 = ms[1][5]
    G["a"] += 1
show("getitem")
reset()
if "a" in G:
    for x in ms[0]:
        G["a"] += x
show("iter")
reset()
if "a" in G:
    u11 = ms[0] < ms[1]
    G["a"] += 1
show("lt")
reset()
if "a" in G:
    u12 = P(ms[0], 1) == P(ms[1], 1)
    G["a"] += 1
show("nt eq")
reset()
if "a" in G:
    u13 = (ms[0], 1) == (ms[1], 1)
    G["a"] += 1
show("tuple eq")
reset()
if "a" in G:
    u14 = repr(P(ms[0], 1))
    G["a"] += 1
show("nt repr")
reset()
o: Optional[M] = ms[2]
if "a" in G:
    if o is not None and o == ms[2]:
        G["a"] += 1
show("opt eq")
reset()
if "a" in G:
    ms.remove(M(3))
    G["a"] += 1
show("remove")
reset()
d2 = {"x": M(1)}
d3 = {"x": M(1)}
if "a" in G:
    u15 = d2 == d3
    G["a"] += 1
show("dict eq")
