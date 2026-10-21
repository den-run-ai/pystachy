# tupleret (tuple_return.calls): run's unpacking takes step's slots by value from @v.f.step, which
# makes no tuple (no pys_alloc); step's own symbol, a wrapper that makes the tuple, is what other
# uses get. pair's only call keeps its tuple, which escapes into a list, and kept returns a tuple
# it did not make: both are lowered as before, each making or returning its tuple.
def step(x: int, y: int) -> tuple[int, int]:
    return (y, (x + y) % 1000003)


def run(n: int) -> int:
    x, y = 0, 1
    for _ in range(n):
        x, y = step(x, y)
    return x


def pair(a: int) -> tuple[int, int]:
    return (a, a)


ORIGIN = (0, 0)


def kept(fresh: bool) -> tuple[int, int]:
    if fresh:
        return (1, 1)
    return ORIGIN


u, v = kept(False)
print(run(10), [pair(1)], u, v)
