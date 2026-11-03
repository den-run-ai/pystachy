# copy.deepcopy() of an object that two fields typed as its base class hold, whose class inherits a
# __deepcopy__() that returns an object of the base class: the memo holds that copy for the second
# field, which gets the same object, as in CPython
import copy


class Base:
    def __init__(self) -> None:
        self.x = 1

    def __deepcopy__(self, memo) -> "Base":
        b = Base()
        b.x = self.x + 10
        return b


class Leaf(Base):
    def __init__(self) -> None:
        super().__init__()
        self.y = 2.5


class Holder:
    def __init__(self, a: Base, b: Base) -> None:
        self.a = a
        self.b = b


leaf = Leaf()
h = copy.deepcopy(Holder(leaf, leaf))
print(type(h.a).__name__, type(h.b).__name__, h.a is h.b, h.a.x, h.a is leaf)
items: list[Base] = [leaf, Base(), leaf]
both = copy.deepcopy(items)
print([type(v).__name__ for v in both], both[0] is both[2], both[0].x, both[1].x)
