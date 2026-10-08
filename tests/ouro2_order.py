from __future__ import annotations

log: list[str] = []
xs = [10, 20, 30]
pos = 0


def note(s: str, v: int) -> int:
    log.append(s)
    return v


def advance() -> int:
    global pos
    pos += 1
    return 100


def get_xs() -> list[int]:
    log.append("xs")
    return xs


def dump() -> None:
    global log
    s = ""
    for e in log:
        s = s + e + " "
    print(s)
    log = []


class Box:
    v: int
    kids: list[int]

    def __init__(self) -> None:
        self.v = 1
        self.kids = [1, 2, 3]


def box() -> Box:
    log.append("box")
    return b


b = Box()
xs[note("i", 0)] = note("v", 5)  # Python evaluates the value before the target
dump()
get_xs()[note("i", 1)] = note("v", 6)
dump()
box().v = note("v", 7)
dump()
xs[pos] = advance()  # the index is read after the call changed it
print(xs[0], xs[1], xs[2], pos, b.v)
xs[pos] += advance()  # here the index is read first, and only once
print(xs[0], xs[1], xs[2], pos)
get_xs()[note("i", 2)] += note("v", 1)
dump()
box().kids[note("i", 0)] *= note("v", 9)
dump()
box().v += note("v", 3)
dump()
print(xs[2], b.kids[0], b.v)
print(note("a", 1), note("b", 2), note("c", 3))  # all arguments are evaluated before printing
dump()
print(note("l", 1) + note("r", 2) * note("m", 3), note("x", 1) < note("y", 2) and note("z", 3) > 0)
dump()
