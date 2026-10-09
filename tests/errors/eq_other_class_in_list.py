# error: eq_other_class_in_list.py:20: error: comparing P objects (in a list, tuple, in, count, index, sort, min or max) calls __eq__() with a P, but it takes a Q
# CPython compares the items of lists and tuples, and the items that in and count look at, with
# P.__eq__ whatever its annotation says; Pystachy can only pass it a Q. (The runtime's equality
# fell back to identity: False False False 0, where CPython prints True True True 1.)
class Q:
    def __init__(self) -> None:
        self.w = 1


class P:
    def __init__(self, v: int) -> None:
        self.v = v

    def __eq__(self, other: Q) -> bool:
        return True


a = P(1)
b = P(2)
print([a] == [b], (a, 1) == (b, 1), a in [b], [b].count(a))
