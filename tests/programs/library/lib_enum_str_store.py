# A StrEnum member where str is annotated, as PEP 484 allows: CPython passes and stores it as it
# is, so a function compiles for the member's class and a variable, field or return holds a
# str | member union, whose member keeps its class and repr() (#1394).
from enum import StrEnum


class Shade(StrEnum):
    DARK = "dark"
    LIGHT = "light"


def greet(s: str) -> str:
    return s.upper() + "!"


def label(s: str) -> str:
    return s


def choose(dark: bool) -> str:
    if dark:
        return Shade.DARK
    return "plain"


class Lamp:
    def __init__(self) -> None:
        self.tone: str = Shade.LIGHT


def local() -> None:
    s: str = Shade.DARK
    print(repr(s), s == "dark", f"[{s}]", len(s), s + "er", s.startswith("d"))


name: str = Shade.LIGHT
print(name, repr(name), str(name), name == "light", isinstance(name, Shade))
name = "other"
print(repr(name), isinstance(name, Shade))
print(greet(Shade.LIGHT), greet("hi"), repr(label(Shade.DARK)), repr(label("x")))
print(repr(choose(True)), repr(choose(False)), repr(Lamp().tone))
local()
