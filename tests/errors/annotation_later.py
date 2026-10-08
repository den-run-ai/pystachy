# error: name 'Box' is not defined (CPython evaluates this annotation when the def statement runs: quote it, or import annotations from __future__)
def unpack(b: Box) -> int:
    return b.v


class Box:
    def __init__(self, v: int):
        self.v = v


print(unpack(Box(1)))
