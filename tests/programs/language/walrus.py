# Assignment expressions bind the name where an assignment would (PEP 572): in the function or
# module code around them, also from a comprehension; their value is the value assigned
import re

data = [3, 0, 7, 12, 5]
if (n := len(data)) > 3:
    print("long", n)
print(n)
lines = ["alpha", "beta", "", "gamma"]
pos = 0


def nxt() -> str:
    global pos
    pos += 1
    return lines[pos - 1] if pos <= len(lines) else ""


while (line := nxt()) != "":
    print("line", line)
print(repr(line), pos)
print([y for x in data if (y := x * 2) > 6], y)
print([last := x for x in data], last)
print(any((w := x) > 5 for x in data), w)
print(all((u := x) < 7 for x in data), u)
print(sum((t := x) for x in data), t)
print({(sv := x % 3) for x in data}, sv)
print((a := 1), a, (a := 2), a)
print(f"{(fs := 'é')}{fs * 2}")
print(data[(ix := 2)], ix)
print({"k": (dv := 4)}, ((tv := 1), tv), dv)
print((outer := (inner := 3) + 1), outer, inner)
print(max(z := 5, 3), z)


def kw(a: int, b: int = 0) -> int:
    return a * 10 + b


print(kw((p := 4), b=(r := p + 1)), p, r)


def total(xs: list[int]) -> int:
    acc = 0
    for x in xs:
        if (sq := x * x) > 10:
            acc += sq
    return acc


print(total(data))


def lookup(d: dict[str, int], k: str) -> str:
    if (v := d.get(k)) is not None:
        return f"{k}={v + 1}"
    return "missing"


print(lookup({"a": 1}, "a"), lookup({"a": 1}, "b"))


def parse(s: str) -> str:
    if m := re.match(r"(\w+)-(\d+)", s):
        return m.group(1) + ":" + m.group(2)
    return "none"


print(parse("abc-12"), parse("!!"))


def comps() -> None:
    print([q := i for i in range(3)], q)
    stuff = [1, 2, 3]
    print((tot := sum(stuff)), tot)
    print([(k, km) for k in "ab" if (km := k.upper()) != "Z"], km)


comps()


def counter() -> None:
    cnt = 0

    def bump() -> int:
        nonlocal cnt
        return (cnt := cnt + 1)

    bump()
    print(bump(), cnt)
    if (got := bump()) == 3:
        def show() -> str:
            return f"got {got}"

        print(show())


counter()
level = 0


def raise_level() -> None:
    global level
    if (level := level + 5) > 3:
        print("level", level)


raise_level()
print(level)


def empty() -> None:
    if not (xs := []):
        xs.append("x")
    print(xs)


empty()


def narrowing(x: int | None) -> None:
    if x is not None:
        print("before", x + 1)
        if (x := None) is None:
            print("now", x)
    print(x)
    if isinstance(v := x, int):
        print("int", v)


narrowing(4)


def stream() -> None:
    vals = [1, 2, None, 4]
    j = 0
    while (v := vals[j]) is not None:
        print("v", v + 1)
        j += 1
    print("stopped at", j, v)


stream()


def template(x):
    if (y := x * 2) > 5:
        return y
    return -y


print(template(3), template(1.5), template(2))
assert (chk := 7) == 7
print(chk)
lam = lambda q: (dbl := q * 2) + dbl
print(lam(4))


def default(a: int = (dflt := 3)) -> int:
    return a


print(default(), dflt)


class Acc:
    def __init__(self) -> None:
        self.items: list[int] = []

    def add_all(self, xs: list[int]) -> int:
        if (k := len(xs)) > 0:
            self.items.extend(xs)
        return k


acc = Acc()
print(acc.add_all([1, 2]), acc.items)
limit: float = 0.0
if (limit := 2.5) > 1:
    print("limit", limit)
print([mt.group(0) for s in ["a1", "b", "c22"] if (mt := re.search(r"\d+", s))])


def present(d: dict[str, int]) -> list[int]:
    return [v + 1 for k in "abc" if (v := d.get(k)) is not None]


print(present({"a": 1, "c": 3}))
