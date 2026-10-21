# generator.throw(e) (#490 stage 3): e is raised at the suspended yield; if the generator
# handles it and yields again, throw() returns that value; if it finishes, StopIteration; else
# the exception comes out of throw(). Thrown into a generator that has not started or has
# finished, the exception is raised as it is; at a yield outside any handler, it leaves the
# generator (a StopIteration as PEP 479's RuntimeError). throw() takes an exception, an
# exception class, or a call of one; user exception classes too.
import os
import tempfile
from collections.abc import Generator, Iterator


def g() -> Iterator[int]:
    try:
        yield 1
        yield 2
    except ValueError as e:
        print("caught", e)
        yield 10
        yield 11
    finally:
        print("finally")


x = g()
print(next(x))
print("throw gives", x.throw(ValueError("boom")))
print(next(x))
try:
    next(x)
except StopIteration:
    print("done")
x = g()
print(next(x))
try:
    x.throw(KeyError("k"))
except KeyError as e:
    print("propagated", repr(e))
print(next(x, -1))
x = g()
try:
    x.throw(ValueError)
except ValueError as e:
    print("not started", repr(e))
print(next(x, -1))


def h() -> Iterator[int]:
    yield 1
    yield 2


y = h()
next(y)
try:
    y.throw(StopIteration)
except RuntimeError as e:
    print("outside a handler:", e)
y = h()
try:
    y.throw(StopIteration)
except StopIteration:
    print("not started: StopIteration as it is")
list(y)
try:
    y.throw(TypeError("t"))
except TypeError as e:
    print("finished:", e)


def ret() -> Iterator[int]:
    try:
        yield 1
    except ValueError:
        return


r = ret()
next(r)
try:
    r.throw(ValueError)
except StopIteration:
    print("throw finished it: StopIteration")


class MyErr(Exception):
    pass


class Detailed(Exception):
    def __init__(self, code: int) -> None:
        super().__init__(f"code {code}")
        self.code = code


def m() -> Iterator[str]:
    while True:
        try:
            yield "ok"
        except MyErr as e:
            print("MyErr", repr(e))
        except Detailed as d:
            print("Detailed", d.code, d)


q = m()
next(q)
print(q.throw(MyErr("one")))
print(q.throw(MyErr))
print(q.throw(Detailed(7)))
err = MyErr("kept")
print(q.throw(err))
q.close()

D = tempfile.mkdtemp()
P = os.path.join(D, "throw.txt")
with open(P, "w") as f:
    f.write("one\ntwo\nthree\n")


def lines() -> Iterator[str]:
    with open(P) as fh:
        for ln in fh:
            yield ln.strip()


ls = lines()
print(next(ls))
try:
    ls.throw(ValueError("in with"))
except ValueError as e:
    print("propagated", e)
print(next(ls, "done"))


def inner() -> Iterator[int]:
    try:
        yield 1
        yield 2
    finally:
        print("inner closed")


def outer() -> Iterator[int]:
    for v in inner():
        try:
            yield v
        except KeyError:
            print("outer caught at", v)
    print("outer loop ended")


o = outer()
print(next(o))
print(o.throw(KeyError("k")))
try:
    o.throw(TypeError("t"))
except TypeError as e:
    print("TypeError out", e)
print(next(o, -1))
sq = (i * i for i in range(5))
next(sq)
try:
    sq.throw(IndexError("ix"))
except IndexError as e:
    print("genexp throw", e)
print(list(sq))


def gexit() -> Iterator[int]:
    try:
        yield 1
    except GeneratorExit:
        print("GeneratorExit thrown")
        yield 2


ge = gexit()
next(ge)
print("throw(GeneratorExit) gives", ge.throw(GeneratorExit))


def rethrow() -> Iterator[int]:
    try:
        yield 1
    except ValueError:
        print("re-raising")
        raise


rt = rethrow()
next(rt)
try:
    rt.throw(ValueError("again"))
except ValueError as e:
    print("re-raised", e)


def nested() -> Iterator[str]:
    try:
        try:
            yield "a"
        finally:
            print("inner finally")
    except OSError as e:
        print("outer caught", e)
        yield "recovered"


n = nested()
next(n)
print(n.throw(OSError(2, "No such file")))
print(next(n, "end"))


def throws_into(other: Generator[int, None, None]) -> Iterator[str]:
    try:
        other.throw(ValueError("from a generator"))
    except ValueError as e:
        yield f"other raised {e}"


t = h()
next(t)
print(list(throws_into(t)))
