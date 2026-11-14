from .helpers import area_of, describe, scaled


class Shape:
    def __init__(self, name: str, w: int, h: int) -> None:
        self.name = name
        self.w = w
        self.h = h

    def area(self) -> int:
        return area_of(self)

    def text(self) -> str:
        return describe(self, None)

    def twice(self) -> "Shape":
        return scaled(self, 2)
