# Names that only an `if TYPE_CHECKING:` block imports type quoted annotations here: Shape is
# the class of a module the program loads anyway (shapes imports this one), Missing names a
# module no code imports.
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .shapes import Shape
    from .never_loaded import Missing


def area_of(shape: "Shape") -> int:
    return shape.w * shape.h


def describe(shape: "Shape", other: "Optional[Shape]") -> str:
    extra = "" if other is None else " with " + other.name
    return shape.name + " " + str(area_of(shape)) + extra


def scaled(shape: "Shape", factor: int) -> "Shape":
    grown: "Shape" = shape
    grown.w *= factor
    grown.h *= factor
    return grown


def label(thing: "Missing") -> str:
    # (each call types it: any object with a name)
    return "<" + thing.name + ">"


def labels(things: "list[Missing]") -> "list[str]":
    return [label(t) for t in things]
