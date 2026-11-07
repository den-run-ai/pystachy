# Gen.tuple_const (tuple_const.calls): a tuple display of literals is a constant tuple of its
# module, which no call makes (no pys_new): zero's, the empty tuple's, nested's, and the
# subscript key's in lookup. either returns a constant or a new tuple: run's unpacking takes its
# slots by value from @v.f.either, which makes no tuple, and the wrapper that other calls get
# makes one only where the body returned no constant. A display of a parameter is made at each
# call (ray), and so is the tuple of *args, which CPython makes at each call (varargs).
# Its return conversion reads that fixed tuple into final VTuple storage (pys_alloc).
def zero() -> tuple[float, float, float]:
    return (0.0, 0.0, 0.0)


def empty() -> tuple[()]:
    return ()


def nested() -> tuple[tuple[int, int], str]:
    return ((1, -2), "x")


def ray(x: float) -> tuple[float, float, float]:
    return (x, 0.0, 0.0)


def either(n: int) -> tuple[int, int]:
    if n > 0:
        return (n, n + 1)
    return (0, 0)


def run(n: int) -> int:
    t = 0
    for i in range(n):
        a, b = either(i % 3)
        t += a + b
    return t


def varargs(*args: int) -> tuple[int, ...]:
    return args


def lookup(d: dict[tuple[int, int], int]) -> int:
    return d[1, 2]


print(zero(), empty(), nested(), ray(1.0), either(0) is either(0), run(10), varargs(1, 2), lookup({(1, 2): 3}))
