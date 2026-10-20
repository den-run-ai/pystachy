# p.__init__(...) of a NamedTuple is object.__init__: tuple.__new__ set the fields as the
# object was made, and the call evaluates its arguments, takes any, and changes nothing (also
# through p.__init__ as a value, a Callable or self.__init__ in a method, and on None).
from typing import Callable, NamedTuple


class P(NamedTuple):
    x: int
    y: int = 7

    def reset(self) -> None:
        print("reset", self.__init__(0, 0), self)


def arg(tag: str, v: int) -> int:
    print("arg", tag)
    return v


def boom() -> int:
    raise ValueError("boom")


p = P(1, 2)
print(p.__init__(3, 4), p)
p.__init__(x=5, y=6)
p.__init__()
p.__init__(1, 2, 3, 4, 5)
p.__init__(z=[1], w={})
p.__init__(*(8, 9))
print(p, p.x, p.y, p[0], p == P(1, 2), p == (1, 2))
for _ in range(3):
    p.__init__(p.x + 10, p.y + 10)
print("repeated", p)

# construction, defaults and _replace() still set the fields
q = P(3)
q.__init__(arg("a", 4), y=arg("b", 5))
print(q, q._replace(y=8), q)
r = q._replace(x=9)
r.__init__(10, 11)
print(r, q, P(y=4, x=3), P(5), P(*(6, 7)))
q.reset()

f = p.__init__
print(f(8, 9), p)
cb: Callable[[int, int], None] = p.__init__
cb(3, 4)
print(p, [g(6, 7) for g in [p.__init__, P(5).__init__]], p)
try:
    p.__init__(boom())
except ValueError as e:
    print("caught", e, p)


def maybe(n: P | None) -> None:
    print("maybe", n.__init__(1, 2), n)


maybe(p)
maybe(None)


def bind(n: P | None) -> None:
    g = n.__init__
    h: Callable[[int, int], None] = n.__init__
    print("bind", g(1, 2), h(3, 4), n)


bind(p)
bind(None)
x, y = p
print(x, y, len(p), list(p))
