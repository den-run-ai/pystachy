# error: annotation_forward_class.py:5: error: name 'C' is not defined (CPython evaluates this annotation when the def statement runs: quote it, or import annotations from __future__)
# CPython 3.13 evaluates a def's annotations when the def statement runs: a class defined after
# it is a NameError there, unless the annotation is a string ("C") or the module imports
# annotations from __future__.
def f(c: C) -> int:
    return c.v


class C:
    def __init__(self) -> None:
        self.v = 3


print(f(C()))
