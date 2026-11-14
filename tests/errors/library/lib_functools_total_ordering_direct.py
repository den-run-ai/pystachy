# error: lib_functools_total_ordering_direct.py:17: error: A.__ge__() returns NotImplemented for these operands, which only a comparison of objects (==, <, ...) reads: calling it directly is not supported
from functools import total_ordering


@total_ordering
class A:
    def __init__(self, n: int) -> None:
        self.n = n

    def __lt__(self, other):
        if not isinstance(other, A):
            return NotImplemented
        return self.n < other.n


xs = [A(1), A(2)]
print(xs[0].__ge__(xs[1]))
