# generator.close() (#490 stage 3): GeneratorExit is raised at the suspended yield, so finally
# blocks, with blocks and except GeneratorExit run; a generator that has not started, or is
# suspended where nothing would see GeneratorExit, or has finished, is just finished. What the
# generator raises as it closes comes out of close() (a StopIteration as PEP 479's RuntimeError),
# a yield after GeneratorExit raises "generator ignored GeneratorExit" and leaves it suspended
# there, and closing a running generator raises ValueError.
import os
import tempfile
from collections.abc import Generator, Iterator


def g1() -> Iterator[int]:
    try:
        yield 1
        yield 2
    finally:
        print("g1 finally")


x = g1()
print(next(x))
x.close()
print("closed", next(x, -1))
x.close()
print("closed twice")
y = g1()
y.close()
print("never started", next(y, -1))


def ign() -> Iterator[int]:
    try:
        yield 1
    except GeneratorExit:
        print("ignoring")
    yield 2
    print("after 2")


z = ign()
next(z)
try:
    z.close()
except RuntimeError as e:
    print("close:", e)
print(next(z, -1))
z2 = ign()
next(z2)
try:
    z2.close()
except RuntimeError as e:
    print("close:", e)
z2.close()
print("suspended at the second yield: closed quietly")


def bad() -> Iterator[int]:
    try:
        yield 1
    finally:
        raise KeyError("cleanup")


b = bad()
next(b)
try:
    b.close()
except KeyError as e:
    print("close raised", repr(e))
print(next(b, -1))


def stop() -> Iterator[int]:
    try:
        yield 1
    finally:
        raise StopIteration


s = stop()
next(s)
try:
    s.close()
except RuntimeError as e:
    print("close raised", repr(e))


class Oops(Exception):
    pass


def custom() -> Iterator[int]:
    try:
        yield 1
    except GeneratorExit:
        raise Oops("while closing")


c = custom()
next(c)
try:
    c.close()
except Oops as e:
    print("custom", repr(e))


def plain() -> Iterator[int]:
    yield 1
    yield 2


p = plain()
next(p)
p.close()
print("plain", next(p, -1))

D = tempfile.mkdtemp()
P = os.path.join(D, "close.txt")
with open(P, "w") as f:
    f.write("a\nb\nc\n")


def lines() -> Iterator[str]:
    with open(P) as fh:
        for ln in fh:
            yield ln.strip()
    print("lines ended")


ls = lines()
print(next(ls), next(ls))
ls.close()
print(next(ls, "none left"))


def selfclose() -> Iterator[int]:
    yield 1
    me.close()
    yield 2


me = selfclose()
next(me)
try:
    next(me)
except ValueError as e:
    print("ValueError:", e)

sq = (i * i for i in range(5))
print(next(sq), next(sq))
sq.close()
print(list(sq))
gens: list[Generator[int, None, None]] = [g1() for _ in range(3)]
for gg in gens:
    next(gg)
for gg in gens:
    gg.close()
print([next(gg, 0) for gg in gens])


def closes_other(other: Generator[int, None, None]) -> Iterator[str]:
    yield "closing"
    other.close()
    yield "closed"


o = g1()
next(o)
print(list(closes_other(o)))
