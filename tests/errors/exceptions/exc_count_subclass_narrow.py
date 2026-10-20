# error: exc_count_subclass_narrow.py:16: error: comparing E objects (in a list, tuple, in, count, index, sort, min or max) calls __eq__() of F with a E, but it takes a F
# xs.count() compares its E items, which may be objects of F, whose __eq__ CPython calls with
# an E whatever its annotation says (CPython prints 1)
class E(Exception):
    def __init__(self, n: int) -> None:
        super().__init__(n)
        self.n = n


class F(E):
    def __eq__(self, other: "F") -> bool:
        return self.n == other.n


xs: list[E] = [F(1), E(2), F(3)]
print(xs.count(E(1)))
