# error: lib_functools_total_ordering_recursive.py:14: error: A.__ge__() returns NotImplemented, which only a comparison of objects (==, <, ...) reads: the call at tests/errors/library/lib_functools_total_ordering_recursive.py:17, which takes its result as it is, is not supported
# A call of a method @total_ordering adds, compiled while that method is (through the class's own
# method, which it calls): the added method returns NotImplemented where the class's own one
# does, which CPython's call gives as it is, so the call is rejected as a direct call is.
from functools import total_ordering


@total_ordering
class A:
    def __init__(self, n: int) -> None:
        self.n = n

    def __lt__(self, other: "A") -> bool:
        if other.n < 0:
            return NotImplemented
        if self.n == 0:
            print("direct:", other.__ge__(A(-1)))
        return self.n < other.n


print(A(0) >= A(1))
