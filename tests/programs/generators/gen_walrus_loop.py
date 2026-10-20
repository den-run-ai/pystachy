# A loop over (g := gen()) does not own the generator: g still holds it after the loop, so
# leaving the loop neither closes nor destroys it (#568).
from collections.abc import Generator, Iterator


def gen(tag: str) -> Iterator[str]:
    try:
        for i in range(5):
            yield tag + str(i)
    finally:
        print("closed", tag)


def f(tag: str) -> Generator[str, None, None]:
    for x in (g := gen(tag)):
        print("first", x)
        break
    return g


def deep(n: int, s: str) -> str:
    return s if n == 0 else deep(n - 1, (s + str(n))[-3:])


gs = [f("a"), f("b")]
print(deep(100, "x"))
for h in gs:
    print(next(h, "done"), list(h))


def outer() -> Iterator[str]:
    yield from (inner := gen("c"))
    print("after", next(inner, "done"))


for y in outer():
    print("got", y)
