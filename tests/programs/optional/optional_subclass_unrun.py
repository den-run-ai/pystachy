# Where a program defines a subclass of ImportError, statements after an optional import's
# imports that never raise one compile and run as before (#1504): through a handler of the
# subclass itself, a lambda or generator body that does not run, a comprehension variable of the
# subclass's name, a decorator, a __post_init__ of a class that is no dataclass, and a package
# whose __init__ catches PackageNotFoundError around version(). The last statement does raise.
from typing import Callable, Iterator
from loader.subimp.errors import Missing


def caught() -> str:
    try:
        raise Missing("inner")
    except Missing:
        return "caught inside"


def fails() -> int:
    raise Missing("never called")


def gen() -> Iterator[int]:
    raise Missing("never iterated")
    yield 1


def deco(f: Callable[[int], int]) -> Callable[[int], int]:
    def wrapped(x: int) -> int:
        if x < 0:
            raise Missing("negative")
        return f(x)

    return wrapped


@deco
def double(x: int) -> int:
    return 2 * x


class Plain:
    def __init__(self, v: int) -> None:
        self.v = v

    def __post_init__(self) -> None:
        raise Missing("Plain is no dataclass")


try:
    import json

    a = caught()
    later = lambda: fails()
    g = gen()
    squares = [Missing * Missing for Missing in range(4)]
    d = double(3)
    p = Plain(5).v
except ImportError:
    a = "handler"
print(a, squares, d, p)

try:
    import loader.subimp.pkg

    v = loader.subimp.pkg.__version__
except ImportError:
    v = "handler"
print(v)

try:
    import json

    n = double(-1)
except ImportError as e:
    n = 0
    print("handler:", e)
print(n)
