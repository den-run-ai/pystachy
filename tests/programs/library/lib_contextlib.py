# lib/contextlib (CPython 3.13's Lib/contextlib.py, ported): @contextmanager's
# _GeneratorContextManager runs the generator to its yield as the with statement enters, throws
# the block's exception in where it is suspended and suppresses it if the generator does,
# raises "generator didn't yield", "generator didn't stop" and "generator didn't stop after
# throw()", lets StopIteration, GeneratorExit and the exceptions the generator raises instead go
# on; a manager decorates a function (@cm()), with keyword arguments too; closing(),
# nullcontext() and suppress(), which a with statement compiles as an except clause; and
# @contextmanager on methods.
from collections.abc import Generator, Iterator
import contextlib
from contextlib import closing, contextmanager, nullcontext, suppress


@contextmanager
def noyield(n: int) -> Iterator[int]:
    if n > 0:
        yield n


@contextmanager
def twice() -> Iterator[int]:
    yield 1
    yield 2


@contextmanager
def swallow(kind: str) -> Iterator[str]:
    try:
        yield kind
    except ValueError as e:
        print("swallowed", e)
    print("after yield", kind)


@contextmanager
def keeps_yielding() -> Iterator[int]:
    try:
        yield 1
    except KeyError:
        yield 2


@contextmanager
def converts() -> Iterator[None]:
    try:
        yield
    except KeyError as e:
        raise IndexError("converted " + str(e))


@contextmanager
def plain() -> Iterator[str]:
    print("setup")
    yield "plain"
    print("teardown")


class Res:
    def __init__(self, name: str) -> None:
        self.name = name

    def close(self) -> None:
        print("closed", self.name)


try:
    with noyield(0):
        print("not reached")
except RuntimeError as e:
    print("RuntimeError", e)
try:
    with twice() as t:
        print("body", t)
except RuntimeError as e:
    print("RuntimeError", e)
with swallow("a") as s:
    print("body", s)
    raise ValueError("v")
print("continued")
try:
    with keeps_yielding():
        raise KeyError("k")
except RuntimeError as e:
    print("RuntimeError", e)
try:
    with converts():
        raise KeyError("k2")
except IndexError as e:
    print("IndexError", e)
try:
    with plain():
        raise StopIteration
except StopIteration:
    print("StopIteration propagated")
try:
    with swallow("b"):
        raise StopIteration
except StopIteration:
    print("StopIteration propagated b")
try:
    with plain():
        raise GeneratorExit
except GeneratorExit:
    print("GeneratorExit propagated")
with closing(Res("r1")) as r:
    print("using", r.name)
try:
    with closing(Res("r2")):
        raise OSError("io")
except OSError as e:
    print("OSError", e)
with nullcontext():
    print("null")
with nullcontext(42) as answer:
    print("null", answer + 1)


def loop() -> int:
    total = 0
    for i in range(5):
        with plain() as p:
            if i == 1:
                continue
            if i == 3:
                break
            total += i
    with plain():
        return total * 10
    return -1


print(loop())


@plain()
def decorated(x: int, y: int) -> int:
    print("decorated", x, y)
    return x + y


print(decorated(1, 2))
print(decorated(3, 4))


def f(s: str) -> int:
    r = -1
    with suppress(ValueError):
        r = int(s)
        print("parsed", r)
    return r


print(f("12"), f("x"))
with suppress(KeyError, IndexError):
    print([1][3])
print("after")
with contextlib.suppress(ZeroDivisionError):
    print(1 // 0)
try:
    with suppress(KeyError):
        raise ValueError("not suppressed")
except ValueError as e:
    print("caught", e)
with suppress():
    print("nothing to suppress")
d = {"a": 1}
with suppress(LookupError):
    v = d["b"]
try:
    print(v)
except NameError as e:
    print("unbound", e)


class Held:
    def __init__(self, name: str) -> None:
        self.name = name

    def __enter__(self) -> "Held":
        print("open", self.name)
        return self

    def __exit__(self, et, ev, tb) -> bool:
        print("close", self.name, et.__name__ if et is not None else None)
        return False


def reader(name: str) -> Iterator[str]:
    with Held(name) as r:
        for i in range(3):
            yield r.name + str(i)


@contextmanager
def ctx2(name: str) -> Iterator[str]:
    print("enter", name)
    try:
        yield name
    finally:
        print("exit", name)


def nested() -> Generator[str, str, None]:
    with ctx2("outer") as o:
        with Held("inner"):
            got = yield o
            print("got", got)
            got = yield got or ""
            print("got2", got)


for x in reader("a"):
    print(x)
g = reader("b")
print(next(g))
g.close()
print("closed b")
g = reader("c")
print(next(g))
try:
    g.throw(ValueError("thrown"))
except ValueError as e:
    print("came out", e)
n = nested()
print(next(n))
print(n.send("hello"))
n.close()
print("closed nested")
n2 = nested()
print(next(n2))
try:
    n2.throw(KeyError("kk"))
except KeyError as e:
    print("KeyError out", e)
for x in reader("d"):
    if x == "d1":
        break
print("done")


@contextmanager
def kw(name: str, times: int = 1) -> Iterator[str]:
    print("kw enter", name, times)
    yield name * times
    print("kw exit", name)


with kw("ab", times=2) as k:
    print(k)
with kw(name="c") as k:
    print(k)


@kw("deco", times=2)
def scaled(a: int, b: int = 2) -> int:
    return a * b


print(scaled(3), scaled(3, b=5))


class Writer:
    # @contextmanager on methods (ast._Unparser's block() and delimit())
    def __init__(self) -> None:
        self.parts: list[str] = []
        self.depth = 0

    @contextmanager
    def block(self, *, extra: str = "") -> Iterator[int]:
        self.parts.append(":" + extra)
        self.depth += 1
        try:
            yield self.depth
        finally:
            self.depth -= 1

    @contextlib.contextmanager
    def delimit(self, start: str, end: str) -> Iterator[None]:
        self.parts.append(start)
        yield
        self.parts.append(end)


w = Writer()
with w.delimit("(", ")"):
    w.parts.append("x")
with w.block() as d1, w.block(extra="!") as d2:
    w.parts.append(str(d1) + str(d2))
try:
    with w.block():
        raise KeyError("in method manager")
except KeyError as e:
    print("caught", e, w.depth)
print("".join(w.parts), w.depth)


# a class with such a method may have subclasses, which inherit or override it: the method
# returns one manager type whatever the object's class (its generator is the object's class's),
# and super().delimit() or Writer.delimit(self) runs the base class's generator
class Pretty(Writer):
    @contextmanager
    def delimit(self, start: str, end: str) -> Iterator[None]:
        self.parts.append(start + start)
        yield
        self.parts.append(end + end)

    def framed(self) -> str:
        with super().delimit("<", ">"):
            with self.delimit("{", "}"):
                with Writer.delimit(self, "|", "|"):
                    self.parts.append("f")
        return "".join(self.parts)


class Plain(Writer):
    pass


def render(o: Writer) -> str:
    with o.delimit("[", "]"):
        with o.block(extra=type(o).__name__) as depth:
            o.parts.append(str(depth))
    return "".join(o.parts)


for o in [Writer(), Pretty(), Plain()]:
    print(render(o))
print(Pretty().framed())


# a manager that @contextmanager makes is entered once: CPython's __enter__ deletes func, args
# and kwds, so that a second with statement raises AttributeError for args, and a decorator of a
# function made from it (its __call__) for func
@contextmanager
def once(tag: str) -> Iterator[str]:
    print("enter", tag)
    yield tag
    print("exit", tag)


reused = once("reused")
with reused as r1:
    print("first", r1)
try:
    with reused as r2:
        print("second", r2)
except AttributeError as e:
    print("AttributeError:", e)


def doubled(n: int) -> int:
    return n * 2


try:
    print(reused(doubled)(4))
except AttributeError as e:
    print("AttributeError:", e)


# a class of no hierarchy, with a defaulted parameter (as contextlib is imported here too)
class Counter:
    def __init__(self) -> None:
        self.n = 0

    @contextlib.contextmanager
    def bump(self, by: int = 1) -> Iterator[int]:
        self.n += by
        try:
            yield self.n
        finally:
            self.n -= by


ctr = Counter()
with ctr.bump() as c1, ctr.bump(by=5) as c2:
    print(c1, c2, ctr.n)
print(ctr.n)
