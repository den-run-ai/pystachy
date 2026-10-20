# atexit (lib/_pystachy_atexit.py, which Pystachy loads for CPython's C module): callbacks run at
# the end of the program, the last registered first, with their arguments, also by name: a
# module's function, a builtin, a bound method, closures, a lambda and a decorated def; one that
# raises, also SystemExit, is reported on stderr and the next one runs; a global read at exit
import atexit
import sys

count = 0


def report() -> None:
    print("count at exit", count)


def boom() -> None:
    raise ValueError("boom")


def leave() -> None:
    sys.exit(3)


def kw(a: int, b: str = "x", *, c: int = 0) -> None:
    print("kw", a, b, c)


class Box:
    def __init__(self, n: int) -> None:
        self.n = n

    def show(self) -> None:
        print("box", self.n)


@atexit.register
def decorated() -> None:
    print("decorated")


def make(tag: str) -> None:
    def inner() -> None:
        print("closure", tag)
    atexit.register(inner)


atexit.register(report)
atexit.register(boom)
atexit.register(leave)
r = atexit.register(kw, 1, c=2)
print(r is kw)
atexit.register(lambda: print("lambda"))
atexit.register(print, "builtin", 1, sep="-")
atexit.register(Box(7).show)
make("a")
make("b")
for i in range(5):
    count += 1
print("main", atexit._ncallbacks(), decorated.__name__)
