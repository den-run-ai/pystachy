# pystachy: ext
from ffi import byvalue


class TooBig(Exception):
    pass


def fib(n: int) -> int:
    if n > 90:
        raise TooBig("fib(" + str(n) + ") does not fit in 64 bits")
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def shout(s: str) -> str:
    return s.upper() + "!"


@byvalue
def total(xs: list[float]) -> float:
    t = 0.0
    for x in xs:
        t += x
    return t
