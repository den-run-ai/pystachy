# error: in_subclass_eq_narrow.py:18: error: comparing Base objects (in a list, tuple, in, count, index, sort, min or max) calls __eq__() of Sub with a Base, but it takes a Sub
# `in` compares the list's Base items, which may be objects of Sub, whose __eq__ CPython calls
# with a Base whatever its annotation says (CPython prints Sub.__eq__ and True)
class Base:
    pass


class Sub(Base):
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other: "Sub") -> bool:
        print("Sub.__eq__")
        return True


xs: list[Base] = [Sub(1)]
print(Base() in xs)
