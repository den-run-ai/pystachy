# generator.send(v) and the value of a yield expression (#490 stage 3): send(v) resumes the
# generator with v as the value of the yield where it is suspended, and returns what it yields
# next; next() sends None. A generator annotated Generator[Y, S, R] takes S, and its yields'
# values are S | None; a non-None value cannot start a generator (TypeError), and a finished
# one raises StopIteration.
from collections.abc import Generator, Iterator


def averager() -> Generator[float, float, None]:
    total = 0.0
    count = 0
    average = 0.0
    while True:
        term = yield average
        if term is None:
            print("got None")
            continue
        total += term
        count += 1
        average = total / count


a = averager()
print(next(a))
print(a.send(10.0))
print(a.send(30.0))
print(next(a))
print(a.send(5.0))


def echo() -> Generator[str, str, int]:
    n = 0
    s = yield "ready"
    while s is not None and s != "stop":
        n += 1
        s = yield "echo " + s
    return n


e = echo()
try:
    e.send("x")
except TypeError as err:
    print(err)
print(e.send(None))
print(e.send("a"))
print(e.send("b"))
try:
    e.send("stop")
except StopIteration:
    print("stopped")
try:
    e.send("again")
except StopIteration:
    print("finished: StopIteration")


def counter() -> Generator[int, int | None, None]:
    i = 0
    while True:
        v = yield i
        i = i + 1 if v is None else v


c = counter()
print(next(c), next(c), c.send(10), next(c), c.send(None))


def plain():
    x = yield 1
    print("x is", x)
    yield 2


p = plain()
print(next(p))
print(p.send(None))


def nums() -> Iterator[int]:
    got = yield 1
    print("next() sends", got)
    print("and so does a loop:", (yield 2))


print(list(nums()))


class Acc:
    def __init__(self) -> None:
        self.items: list[str] = []

    def run(self) -> Generator[int, str, None]:
        while True:
            s = yield len(self.items)
            if s is not None:
                self.items.append(s)


acc = Acc()
g = acc.run()
print(next(g))
print(g.send("x"), g.send("y"), next(g))
print(acc.items)
gs = [acc.run() for _ in range(3)]
for q in gs:
    next(q)
for i, q in enumerate(gs):
    print(q.send(str(i)))
print(acc.items)
only_next: Generator[int, None, None] = gs[0]
print(next(only_next))


def lister() -> Generator[int, list[int], None]:
    total: list[int] = []
    while True:
        xs = yield len(total)
        if xs is not None:
            total.extend(xs)


ls = lister()
next(ls)
for i in range(200):
    ls.send([i, i + 1])
print(next(ls))


def pairs() -> Generator[tuple[int, str], str, None]:
    n = 0
    while True:
        s = yield (n, "x")
        n += 1
        if s is not None:
            print("pair got", s)


pp = pairs()
print(next(pp), pp.send("q"), next(pp))


def selfish() -> Generator[int, int, None]:
    while True:
        v = yield 0
        if v is not None and v > 1:
            me.send(1)


me = selfish()
next(me)
try:
    me.send(5)
except ValueError as err:
    print("ValueError:", err)


def printer() -> Generator[None, str, None]:
    while True:
        line = yield
        print("printer:", line)


pr = printer()
pr.send(None)
pr.send("hello")
pr.send("world")
pr.close()
lam = lambda: (yield 3)
print(list(lam()))


def sums(n: int) -> Generator[int, int, str]:
    total = 0
    for _ in range(n):
        v = yield total
        total += v if v is not None else 100
    return f"total {total}"


sg = sums(3)
next(sg)
sg.send(1)
sg.send(2)
try:
    sg.send(3)
except StopIteration:
    print("sums finished")
