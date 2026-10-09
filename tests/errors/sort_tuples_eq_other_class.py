# error: sort_tuples_eq_other_class.py:21: error: comparing P objects (in a list, tuple, in, count, index, sort, min or max) calls __eq__() with a P, but it takes a Q
# Sorting tuples compares their items with == before <, so the sort calls P.__eq__ with a P,
# which its annotation does not take (it compared identities: the output was [1, 0]).
class Q:
    def __init__(self) -> None:
        self.z = 5


class P:
    def __init__(self, x: int) -> None:
        self.x = x

    def __eq__(self, other: "Q") -> bool:
        return True

    def __lt__(self, other: "P") -> bool:
        return self.x < other.x


xs = [(P(2), 1), (P(2), 0)]
xs.sort()
print([t[1] for t in xs])
