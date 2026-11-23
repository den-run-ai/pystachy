# error: assigning class attribute 'unit' through T, which inherits it from Base, is not supported
# A class attribute that an ordinary class binds is assigned through it, not through a class
# template under it (#962), as not through an ordinary subclass: CPython would give T an attribute
# of its own.
class Base:
    unit = "cm"

    def __init__(self) -> None:
        self.n = 0


class T(Base):
    def __init__(self, v):
        super().__init__()
        self.v = v


t = T(3)
T.unit = "in"
print(T.unit, t.unit, Base.unit)
