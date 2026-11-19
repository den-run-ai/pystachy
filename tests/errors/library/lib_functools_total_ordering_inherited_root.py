# error: lib_functools_total_ordering_inherited_root.py:17: error: @total_ordering of class A is not supported where it inherits __lt__ from Base: CPython's decorator computes __le__ and __ge__ from that method, not from __gt__ of its body
# CPython's total_ordering() computes the ordering methods a class lacks from the greatest it has,
# __lt__ before __le__, __gt__ and __ge__: here A's __le__ and __ge__ from Base's __lt__, not from
# the __gt__ of A's body, which is all the compiler reads to write them.
from functools import total_ordering


class Base:
    def __init__(self, n: int) -> None:
        self.n = n

    def __lt__(self, other: "Base") -> bool:
        return self.n < other.n


@total_ordering
class A(Base):
    def __gt__(self, other: "Base") -> bool:
        return self.n > other.n * 10


print(A(1) <= A(2))
