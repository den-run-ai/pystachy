# error: lib_functools_total_ordering_assigned.py:14: error: @total_ordering of class A, whose body assigns __lt__, is not supported (the decorator reads the methods that def statements of the body define)
from functools import total_ordering


def before(a: "A", b: "A") -> bool:
    return a.n < b.n


@total_ordering
class A:
    def __init__(self, n: int) -> None:
        self.n = n

    __lt__ = before


print(A(1) >= A(2))
