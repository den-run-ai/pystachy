# error: annotation_own_class.py:8: error: name 'P' is not defined (CPython evaluates this annotation when the def statement runs: quote it, or import annotations from __future__)
# A method's annotation that names its own class, unquoted: the class statement has not bound
# the name yet when CPython 3.13 evaluates it.
class P:
    def __init__(self, v: int) -> None:
        self.v = v

    def same(self, other: P) -> bool:
        return self.v == other.v


print(P(1).same(P(1)))
