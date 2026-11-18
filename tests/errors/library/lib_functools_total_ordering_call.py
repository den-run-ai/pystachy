# error: lib_functools_total_ordering_call.py:13: error: total_ordering(...) as a call is not supported: the compiler applies it where it decorates a class statement (@total_ordering)
from functools import total_ordering


class A:
    def __init__(self, n: int) -> None:
        self.n = n

    def __lt__(self, other: "A") -> bool:
        return self.n < other.n


B = total_ordering(A)
print(B(1) >= B(2))
