# error: lib_functools_total_ordering_inherited.py:16: error: @total_ordering of class A is not supported where it inherits __lt__ from Base: CPython's decorator computes __le__, __gt__ and __ge__ from that method
# CPython's total_ordering() computes the ordering methods a class lacks from the greatest it has,
# which may be inherited (A's from Base's __lt__); the compiler computes them from its body's only.
from functools import total_ordering


class Base:
    def __init__(self, n: int) -> None:
        self.n = n

    def __lt__(self, other: "Base") -> bool:
        return self.n < other.n


@total_ordering
class A(Base):
    pass


print(A(1) >= A(2))
