"""Classes and functions that other modules use, in annotations, containers and comparisons."""
from dataclasses import dataclass
import math as m

__all__ = ["Square", "area", "Circle", "biggest"]
print("mods.shapes: init", __name__)


@dataclass
class Square:
    side: int

    def __lt__(self, other: "Square") -> bool:
        return self.side < other.side


class Circle:
    def __init__(self, r: float):
        self.r = r

    def __repr__(self) -> str:
        return f"Circle({self.r})"


class Opaque:
    def __init__(self) -> None:
        self.v = 1


def area(s: Square) -> int:
    return s.side * s.side


def circle_area(c: Circle) -> float:
    return round(m.pi * c.r * c.r, 3)


def biggest(xs: list[Square]) -> Square:
    return max(xs)


def helper() -> str:
    return "shapes.helper"


x = 5
_private = 7
