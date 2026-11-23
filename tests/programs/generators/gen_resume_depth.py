import sys
from collections.abc import Iterator


def values(n: int) -> Iterator[int]:
    if n:
        child = values(n - 1)
        yield next(child)
    yield n


# Attempt a resume inside the deepest frame. A failed entry finishes g even
# if it has already yielded. A fresh generator can run once callers unwind.
def at_limit(g: Iterator[int]) -> int:
    try:
        return at_limit(g)
    except RecursionError:
        try:
            return next(g)
        except RecursionError:
            return -10


original = sys.getrecursionlimit()
sys.setrecursionlimit(40)
for started in (False, True):
    g = values(2)
    if started:
        print("started", next(g))
    print("at limit", at_limit(g))
    print("after", next(g, -20))
    h = values(2)
    print("fresh", next(h), next(h), next(h, -20))
sys.setrecursionlimit(original)
