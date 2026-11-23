# pystachy: dynamic-any
# send() and close() of a generator held in Any run as typed code's: a sent value reaches the
# yield where the generator is suspended, send(None) is next(), a just-started generator takes
# only None, a value sent to one that reads none is dropped, and close() runs its cleanup; other
# arguments raise CPython's TypeError.
from typing import Any, Generator


def echo() -> Generator[str, str, None]:
    got = yield "ready"
    while True:
        print("got", got)
        got = yield got.upper()


def count() -> Any:
    n = 0
    try:
        while True:
            yield n
            n += 1
    finally:
        print("cleanup")


g: Any = echo()
print(next(g), g.send("hi"), g.send("there"))
c: Any = count()
print(c.send(None), next(c), c.send(None))
c.close()
try:
    next(c)
except StopIteration:
    print("stopped")
fresh: Any = count()
try:
    fresh.send("x")
except TypeError as error:
    print("TypeError", error)
try:
    fresh.send()
except TypeError as error:
    print("TypeError", error)
try:
    fresh.close(1)
except TypeError as error:
    print("TypeError", error)
d: Any = count()
print(next(d), d.send("ignored"), d.send(5))
d.close()
d.close()
print("done")
