# Closing a generator that delegates with yield from to a generator the program also holds
# (#490): the inner generator is closed with it, as CPython's close() closes the generator it
# delegates to, so later next() calls find it finished; a generator closed while suspended where
# closing runs none of its code is finished too.
from collections.abc import Generator, Iterator


def naturals() -> Iterator[int]:
    i = 0
    while True:
        yield i
        i += 1


def guarded() -> Iterator[int]:
    try:
        yield 10
        yield 11
    finally:
        print("guarded closed")


def outer(g: Generator[int, None, None]) -> Iterator[int]:
    yield from g


g = naturals()
for x in outer(g):
    print("x", x)
    if x == 2:
        break
print(next(g, -1), next(g, -1))
h = naturals()
print(next(h))
try:
    for y in outer(h):
        print("y", y)
        raise ValueError("stop")
except ValueError:
    print("caught")
print(next(h, -1))
k = guarded()
for z in outer(k):
    print("z", z)
    break
print(next(k, -1))
