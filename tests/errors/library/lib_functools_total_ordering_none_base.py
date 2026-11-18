# error: lib_functools_total_ordering_none_base.py:13: error: ValueError: must define at least one ordering operation: < > <= >=
# A class that neither defines nor inherits one of __lt__, __le__, __gt__ and __ge__: CPython's
# total_ordering() raises this ValueError as the class statement runs.
from functools import total_ordering


class Base:
    def __init__(self, n: int) -> None:
        self.n = n


@total_ordering
class A(Base):
    def __eq__(self, other: object) -> bool:
        return isinstance(other, A) and self.n == other.n


print(A(1) == A(1))
