# send(), throw() and close() in a program without try or with statements (#490 stage 3): no
# yield is in a handler, so close() finishes a generator without running it, and throw() raises
# the exception as it leaves the generator, here ending the program as CPython does.
from collections.abc import Generator, Iterator


def acc() -> Generator[int, int, str | None]:
    total = 0
    while True:
        v = yield total
        if v is None:
            return "total " + str(total)
        total += v


a = acc()
print(next(a))
print(a.send(5))
print(a.send(7))
r = acc()
next(r)
r.close()
print(next(r, -1))


def letters() -> Iterator[str]:
    x = yield "a"
    print("x:", x)
    yield "b"


g = letters()
print(next(g))
print(next(g))
g.close()
print(list(g))
h = letters()
print(h.throw(KeyError("end")))
