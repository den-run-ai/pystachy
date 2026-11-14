# pystachy: dynamic-any
# Callers that no call op names (constargs, docs/typed-ir.md): a function passed as a value,
# a bound method, a closure, a method that a dynamic value reaches by name, a generator and
# an override. Each of them gives a parameter what the direct calls never do.
from typing import Any, Callable


def render(text: str, loud: bool = False, mark: str | None = None) -> str:
    if loud:
        text = text.upper()
    if mark is not None:
        text = mark + text
    return text


def through(f: Callable[[str, bool, str | None], str]) -> str:
    return f("callable", True, ">")


class Shape:
    def __init__(self, name: str) -> None:
        self.name = name

    def describe(self, full: bool = False, prefix: str | None = None) -> str:
        out = self.name
        if full:
            out += " (" + self.kind() + ")"
        if prefix is not None:
            out = prefix + out
        return out

    def kind(self) -> str:
        return "shape"


class Square(Shape):
    def kind(self) -> str:
        return "square"

    def describe(self, full: bool = False, prefix: str | None = None) -> str:
        return "[" + Shape.describe(self, full, prefix) + "]"


def by_name(o: Any) -> str:
    return o.describe(True, "any ")


def make(scale: int, offset: int = 0, clamp: bool = False) -> Callable[[int], int]:
    def inner(x: int, twice: bool = False) -> int:
        y = x * scale + offset
        if twice:
            y *= 2
        if clamp and y > 10:
            y = 10
        return y
    return inner


def numbers(n: int, evens: bool = False, start: int = 0):
    for i in range(start, n):
        if evens and i % 2:
            continue
        yield i


def guarded(text: str, strict: bool = False, default: int | None = None) -> int:
    try:
        return int(text)
    except ValueError:
        if strict:
            raise
        if default is not None:
            return default
        return -1
    finally:
        if strict:
            print("strict was on")


def main() -> None:
    print(render("direct"))
    print(through(render))
    shapes: list[Shape] = [Shape("s"), Square("q")]
    for s in shapes:
        print(s.describe())
    bound = shapes[1].describe
    print(bound(True))
    print(by_name(shapes[0]), by_name(shapes[1]))
    f = make(3)
    g = make(4, 1, True)
    print(f(2), g(2), g(5))
    print(list(numbers(5)), list(numbers(6, True)), list(numbers(4, start=2)))
    print(guarded("12"), guarded("x"), guarded("y", default=3))
    try:
        guarded("z", True)
    except ValueError:
        print("raised")


main()
