# Name bindings: functions and classes used before their def runs (but called after),
# comprehension variables shadowing the iterable, class bodies in order, import forms
from __future__ import annotations
import dataclasses
from dataclasses import dataclass as dc


def log(s: str) -> int:
    print("eval", s)
    return len(s)


def helper(n: int) -> int:
    return n * 2


def main() -> None:
    print(helper(3), Box(2).w, Pair(1, 2), Single(5))


class Box:
    def __init__(self, w: int):
        self.w = w


@dataclasses.dataclass
class Pair:
    a: int
    b: int


@dc
class Single:
    v: int


class Ordered:
    a: int = log("a")

    def f(self, x: int = log("ff")) -> int:
        return x

    b: int = log("bbb")


x = "outer"


def comp(x: list[str]) -> list[str]:
    return [x + "!" for x in x]


def nested(n: int) -> list[list[int]]:
    return [[y for y in range(y)] for y in range(n)]


def repr(v: int) -> str:
    return "user repr"


main()
print(comp(["p", "q"]), nested(3), Ordered().a, Ordered().f(), Ordered().b)
print(Pair(3, 4), f"{7!r}", repr(1), x)
