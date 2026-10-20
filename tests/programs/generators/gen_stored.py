# Generator objects as values (#490): kept in variables, lists and fields, passed to functions
# and returned, resumed by later loops where an earlier one stopped; a finished generator stays
# finished. A loop over a generator it did not make does not close it.
from collections.abc import Iterator


def naturals() -> Iterator[int]:
    n = 0
    while True:
        print("  produce", n)
        yield n
        n += 1


def word(w: str) -> Iterator[str]:
    for c in w:
        yield c


def step(g: Iterator[str]) -> str:
    # the next item, "" when it has finished
    for c in g:
        return c
    return ""


def total(g: Iterator[int], n: int) -> int:
    s = 0
    for x in g:
        s += x
        n -= 1
        if n == 0:
            break
    return s


class Reader:
    def __init__(self, g: Iterator[str]) -> None:
        self.g = g
        self.seen = 0

    def take(self) -> str:
        c = step(self.g)
        if c != "":
            self.seen += 1
        return c


for x in naturals():
    if x == 2:
        break
    print("first loop", x)
g = naturals()
for x in g:
    if x == 1:
        break
for x in g:
    print("resumed at", x)
    break
print(total(g, 3), total(g, 2))
gens = [word("abc"), word("de"), word("f")]
out = ""
live = True
while live:
    live = False
    for w in gens:
        c = step(w)
        if c != "":
            out += c
            live = True
print(out)
r = Reader(word("xyz"))
print(r.take(), r.take(), r.take(), repr(r.take()), r.seen)
done = word("q")
print(list(done), list(done), sum(1 for _ in done))
