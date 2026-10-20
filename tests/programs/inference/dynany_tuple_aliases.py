# pystachy: dynamic-any
# A tuple converted item by item to and from Any items holds the same objects: an object of the
# program's classes and a list[Any] are boxed and unboxed by reference, not copied, so a change
# made through either tuple shows in the other and in the original; None items stay None
from typing import Any


class Box:
    def __init__(self, n: int) -> None:
        self.n = n


def wrap(b: Box) -> tuple[int, Any]:
    return 1, b


def unwrap(t: tuple[int, Any]) -> tuple[int, Box]:
    return t


b = Box(1)
t = wrap(b)
print(t[1] is b)
t[1].n = 5
print(b.n)
u = unwrap(t)
print(u[1] is b)
u[1].n = 7
print(b.n, t[1].n)

xs: list[Any] = [1, 2]
p: tuple[str, Any] = ("k", xs)
p[1].append(3)
print(xs, p[1] is xs)


def as_list(p: tuple[str, Any]) -> tuple[str, list[Any]]:
    return p


q = as_list(p)
q[1].append(4)
print(xs, q[1] is xs)
n: tuple[int | None, Any] = (None, None)
print(n, n[0] is None, n[1] is None)
