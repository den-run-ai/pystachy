# error: lib_functools_total_ordering_inherited.py:14: error: @total_ordering of class A, whose body defines none of __lt__, __le__, __gt__ and __ge__, is not supported (an inherited one is not read)
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
