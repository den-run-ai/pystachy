# A function that is an item of a tuple display becomes the Callable that the tuple's expected
# type has there (#245), as a list display's items and a dict display's values already do: from
# an annotation, a list or dict display's item type, a parameter, a return, a nested tuple and
# a list's append(). Lambdas, closures, bound methods and builtins too.
from typing import Callable


def a() -> None:
    print("a")


def b() -> None:
    print("b")


def sq(x: int) -> int:
    return x * x


def double(x: int) -> int:
    return 2 * x


# the issue's test runner: a list of (name, function) pairs
tests: list[tuple[str, Callable[[], None]]] = [("a", a), ("b", b)]
for name, fn in tests:
    print(name, end=": ")
    fn()

# an annotated tuple, and one assigned again
pair: tuple[str, Callable[[], None]] = ("a", a)
pair[1]()
pair = ("b", b)
print(pair[0], end=" ")
pair[1]()
print(pair[1] == b, pair[1] == a)

# a dict display's values
table: dict[str, tuple[int, Callable[[int], int]]] = {"sq": (1, sq), "double": (2, double)}
for k in sorted(table):
    n, f = table[k]
    print(k, n, f(7))


# a parameter, and a return
def run(p: tuple[str, Callable[[int], int]], x: int) -> str:
    return p[0] + "=" + str(p[1](x))


def pick(big: bool) -> tuple[str, Callable[[int], int]]:
    if big:
        return ("sq", sq)
    return ("double", double)


print(run(("sq", sq), 5), run(("double", double), 5))
print(run(pick(True), 9), run(pick(False), 9))

# nested tuples, and a list's append()
nested: tuple[tuple[str, Callable[[], None]], int] = (("a", a), 1)
nested[0][1]()
print(nested[1])
more: list[tuple[str, Callable[[int], int]]] = []
more.append(("sq", sq))
more.append(("double", double))
print([p[0] + ":" + str(p[1](3)) for p in more])

# Callable | None
opt: list[tuple[str, Callable[[], None] | None]] = [("a", a), ("none", None), ("b", b)]
for name, g in opt:
    if g is None:
        print(name, "is None")
    else:
        print(name, end=" -> ")
        g()


# lambdas, a closure, a bound method and a builtin
def adder(k: int) -> Callable[[int], int]:
    def add(x: int) -> int:
        return x + k

    return add


class Scale:
    def __init__(self, f: int) -> None:
        self.f = f

    def apply(self, x: int) -> int:
        return x * self.f


def plus10(x: int) -> int:
    return x + 10


def closure_pair(k: int) -> tuple[str, Callable[[int], int]]:
    def add(x: int) -> int:
        return x + k

    return ("add" + str(k), add)


s3 = Scale(3)
ops: list[tuple[str, Callable[[int], int]]] = [
    ("inc", lambda x: x + 1),
    ("neg", lambda x: -x),
    ("add5", adder(5)),
    ("scale3", s3.apply),
    ("abs", abs),
    ("plus10", plus10),
    closure_pair(100),
]
for name, op in ops:
    print(name, op(-4))
lens: tuple[str, Callable[[str], int]] = ("len", len)
print(lens[0], lens[1]("hello"))
