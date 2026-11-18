# error: cmp_notimplemented_call.py:14: error: V.__lt__() returns NotImplemented for these operands, which only a comparison of objects (==, <, ...) reads: calling it directly is not supported
class V:
    def __init__(self, n: int) -> None:
        self.n = n

    def __lt__(self, other):
        if not isinstance(other, V):
            return NotImplemented
        return self.n < other.n


def less(a: V, b: V) -> bool:
    # (b may be None, which the method declines: CPython's call returns NotImplemented)
    return a.__lt__(b)


print(less(V(1), V(2)))
