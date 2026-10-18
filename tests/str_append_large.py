# strs that appends in place (#112) grow across 8,200 bytes, the largest size class, where a copy
# is a large object (#567): the first large copy fits exactly, later ones get room, which the
# collector gives back once a str stops growing. Strs grown just past the boundary and far past it,
# kept in lists, then read, sliced, compared, hashed and grown again; reads between appends,
# s += s and generators.
from collections.abc import Iterator


def cross(base: int, tail: str) -> str:
    s = "c" * base  # (not an append's: the first append copies it)
    s += "|"
    s += tail
    return s


def grow(n: int, piece: str) -> str:
    s = ""
    for _ in range(n):
        s += piece
    return s


def check(name: str, xs: list[str]) -> None:
    total = 0
    for x in xs:
        total += len(x) + ord(x[-1]) + ord(x[len(x) // 2])
    print(name, len(xs), total, xs[0][:6], xs[-1][-6:])


def boundary() -> None:
    out: list[str] = []
    for base in range(8160, 8230, 3):
        out.append(cross(base, str(base)))
    check("cross", out)
    print(out[0] == "c" * 8160 + "|8160", out[5][8170:], len(out[-1]))
    print(sorted([len(x) for x in out])[:4], out[3] < out[4], out[4] > out[3])
    d: dict[str, int] = {}
    for i in range(len(out)):
        d[out[i]] = i
    print(len(d), d[cross(8172, "8172")], cross(8160, "8160") in d)


def far() -> None:
    out: list[str] = []
    for i in range(40):
        out.append(grow(100 + 37 * i, "%09d|" % i))
    check("far", out)
    print(out[7][:20], out[7][-20:], out[7].count("|"), out[39].endswith("000000039|"))
    print(out[11][8195:8205], out[11][16390:16410], out[11][::4097])


def read_between() -> None:
    s = ""
    seen: list[str] = []
    for i in range(3000):
        s += "%05d," % i
        if i % 700 == 699:
            seen.append(s)  # (it keeps the str: the next append copies it)
            y = s
            s += "+"
            print(len(y), len(s), y is s, y == s[:-1], y[-7:], s[-7:])
    for t in seen:
        print(len(t), t[-12:], t.count(","))
    s += s
    print(len(s), s[17998:18010], s[-6:])
    u = s
    u += s  # (s is read: u's str is copied)
    print(len(u), len(s), u[:6], u[-6:], u == s + s)


def regrow() -> None:
    # a kept str grown again: it was read, so the next appends copy it
    s = grow(2500, "ab|")
    first = s
    for i in range(1000):
        s += "z%d" % (i % 10)
    print(len(first), len(s), first == s[: len(first)], s[-10:], first[-6:])
    keep: list[str] = []
    for j in range(5):
        keep.append(s)
        s += "-" * 9000
        s += str(j)
    print([len(k) for k in keep], len(s), s[-12:], keep[2][-3:])


def chunks(n: int) -> Iterator[str]:
    s = ""
    for i in range(n):
        s += "%04d " % i
        if len(s) > 12000:
            yield s
            s = "#"
    yield s


def gens() -> None:
    got = list(chunks(9000))
    print(len(got), [len(g) for g in got[:3]], got[-1][-10:], sum([len(g) for g in got]))


boundary()
far()
read_between()
regrow()
gens()
