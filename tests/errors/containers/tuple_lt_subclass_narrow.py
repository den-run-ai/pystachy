# error: tuple_lt_subclass_narrow.py:16: error: comparing Base objects (in a list, tuple, in, count, index, sort, min or max) calls __lt__() of Sub with a Base, but it takes a Sub
# the tuples' second items may be objects of Sub, whose __lt__ CPython calls with a Base
# whatever its annotation says (CPython prints True)
class Base:
    def __init__(self, n: int) -> None:
        self.n = n


class Sub(Base):
    def __lt__(self, other: "Sub") -> bool:
        return self.n < other.n


a: tuple[int, Base] = (1, Sub(1))
b: tuple[int, Base] = (1, Base(2))
print(a < b)
