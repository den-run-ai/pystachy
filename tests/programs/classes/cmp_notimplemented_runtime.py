# Methods that decide at run time whether to return NotImplemented, with annotated operands: the
# reflected method runs next, then identity (==, !=) or TypeError (<), as CPython.
class Picky:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other: "Picky") -> bool:
        print("Picky.__eq__", self.n)
        if other is None or other.n < 0 or self.n < 0:
            return NotImplemented
        return self.n == other.n

    def __lt__(self, other: "Picky") -> bool:
        print("Picky.__lt__", self.n)
        if other is None or other.n < 0:
            return NotImplemented
        return self.n < other.n

    def __gt__(self, other: "Picky") -> bool:
        print("Picky.__gt__", self.n)
        if other.n > 100:
            return NotImplemented
        return self.n > other.n


p = [Picky(v) for v in [1, -1, 200, 1]]
print(p[0] == p[3], p[0] == p[1], p[1] == p[1], p[1] == Picky(-1), p[0] != p[1])
print(p[0] < p[2], p[2] < p[0], p[0] > p[3])
for i, j in [(2, 1), (1, 2), (0, 2)]:
    try:
        print(p[i] < p[j])
    except TypeError as e:
        print("TypeError", e)
    try:
        print(p[i] > p[j])
    except TypeError as e:
        print("TypeError", e)
