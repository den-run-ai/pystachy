# error: lt_other_class.py:17: error: __lt__() of P takes a Q, not a P
# P defines __lt__, but for a Q: the error says so (it said that '<' is not supported between
# instances of 'P' and 'P').
class Q:
    def __init__(self) -> None:
        self.w = 1


class P:
    def __init__(self, v: int) -> None:
        self.v = v

    def __lt__(self, other: Q) -> bool:
        return self.v < 5


print(P(1) < P(2))
