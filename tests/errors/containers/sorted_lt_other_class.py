# error: sorted_lt_other_class.py:17: error: comparing P objects (in a list, tuple, in, count, index, sort, min or max) calls __lt__() with a P, but it takes a Q
# sorted() orders P objects with P.__lt__, which CPython calls whatever its annotation says;
# Pystachy can only pass it a Q. (It compiled a TypeError that CPython does not raise.)
class Q:
    def __init__(self) -> None:
        self.w = 1


class P:
    def __init__(self, v: int) -> None:
        self.v = v

    def __lt__(self, other: Q) -> bool:
        return self.v < 5


ys = sorted([P(2), P(1)])
print(len(ys))
