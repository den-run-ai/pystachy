from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .shapes import Shape


def widest(a: Shape, b: Shape) -> Shape:
    best: Shape = a
    if b.w > a.w:
        best = b
    return best


class Box:
    def __init__(self, inner: Shape) -> None:
        self.inner: Shape = inner

    def area(self) -> int:
        return self.inner.w * self.inner.h
