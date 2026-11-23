from enum import Enum


class Palette:
    kind = Color


class Color(Enum):
    RED = 1


print(Palette.kind)
