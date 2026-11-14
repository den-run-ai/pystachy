# error: lib_functools_total_ordering_none.py:6: error: ValueError: must define at least one ordering operation: < > <= >=
from functools import total_ordering


@total_ordering
class A:
    def __init__(self, n: int) -> None:
        self.n = n


print(A(1).n)
