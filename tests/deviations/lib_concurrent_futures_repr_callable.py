# Documented deviation: a future's repr names the class of its result
# (lib/compatibility.md#concurrentfutures). An object whose class defines __call__ is shown as a
# function, which a function is too; CPython prints " returned Adder>" first
from concurrent.futures import ThreadPoolExecutor


class Adder:
    def __init__(self, n: int) -> None:
        self.n = n

    def __call__(self, x: int) -> int:
        return x + self.n


def make(n: int) -> Adder:
    return Adder(n)


def inc(x: int) -> int:
    return x + 1


def pick():
    return inc


with ThreadPoolExecutor(max_workers=2) as pool:
    f = pool.submit(make, 3)
    g = pool.submit(pick)
print(f.result()(4), g.result()(4))
r = repr(f)
print(r[r.index(" returned"):])
r = repr(g)
print(r[r.index(" returned"):])
