# yield from as PEP 380 delegates (#490 stage 3): send() and throw() of the delegating generator
# go to the generator it delegates to, whose value then is the delegating generator's; a
# GeneratorExit thrown, or close(), closes the delegate first, and what closing it raises is
# raised in the delegating generator, whose handlers see it; when the delegate finishes, its
# return value is the value of yield from, also through throw().
from collections.abc import Generator, Iterator


def inner() -> Generator[str, str, int]:
    n = 0
    try:
        while True:
            v = yield f"inner got {n}"
            if v is None:
                break
            print("inner received", v)
            n += 1
    except ValueError as e:
        print("inner caught", e)
        yield "after ValueError"
    finally:
        print("inner finally")
    return n


def outer() -> Generator[str, str, None]:
    try:
        r = yield from inner()
        print("inner returned", r)
        yield "outer continues"
    except KeyError as e:
        print("outer caught", repr(e))
        yield "outer handled"
    finally:
        print("outer finally")


g = outer()
print(next(g))
print(g.send("a"))
print(g.send("b"))
print(g.throw(ValueError("v")))
print(next(g))
print(next(g, "end"))
g = outer()
next(g)
print(g.throw(KeyError("k")))
g.close()
print("--- close")


def sub2() -> Iterator[int]:
    try:
        yield 1
    finally:
        print("sub2 finally raises")
        raise KeyError("from sub2")


def top2() -> Iterator[int]:
    try:
        yield from sub2()
    except KeyError as e:
        print("top2 saw", repr(e))
        yield 99


t = top2()
print(next(t))
try:
    t.close()
except RuntimeError as e:
    print("close:", e)
t = top2()
next(t)
print("throw(GeneratorExit) gives", t.throw(GeneratorExit))


def stubborn() -> Iterator[int]:
    try:
        yield 1
    except GeneratorExit:
        yield 2


def wraps_stubborn() -> Iterator[int]:
    try:
        yield from stubborn()
    except RuntimeError as e:
        print("delegating generator saw", e)


w = wraps_stubborn()
next(w)
w.close()
print("--- deep")


def deep() -> Generator[str, str, str]:
    s = yield "d0"
    while s is not None:
        s = yield "deep " + s
    return "deep done"


def mid() -> Generator[str, str, None]:
    r = yield from deep()
    yield "mid end: " + r


def top() -> Generator[str, str, None]:
    yield from mid()


tp = top()
print(next(tp), tp.send("a"), tp.send("b"), next(tp))
print(next(tp, "exhausted"))


def ret_on_throw() -> Generator[str, None, str]:
    try:
        yield "one"
    except ValueError:
        return "returned on ValueError"
    return "plain"


def catcher() -> Iterator[str]:
    r = yield from ret_on_throw()
    yield r


ct = catcher()
next(ct)
print(ct.throw(ValueError))


def numbers() -> Iterator[int]:
    yield from [1, 2, 3]


def wrap_numbers() -> Iterator[int]:
    try:
        yield from numbers()
    except ZeroDivisionError:
        yield -1


wn = wrap_numbers()
print(next(wn), wn.throw(ZeroDivisionError), next(wn, 0))


def from_genexp() -> Generator[int, int, None]:
    yield from (i * 10 for i in range(3))


fg = from_genexp()
print(next(fg), fg.send(5), fg.send(6), next(fg, -1))
