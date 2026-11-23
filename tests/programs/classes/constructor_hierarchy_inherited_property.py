# A class template under an ordinary class (#962) whose __init__ assigns through its base's
# property: the setter runs (stored is set), and value is no field of its own.
class Base:
    def __init__(self) -> None:
        self.stored = 0

    @property
    def value(self):
        return self.stored

    @value.setter
    def value(self, value):
        self.stored = value


class Child(Base):
    def __init__(self, value):
        self.value: int = value


c = Child(3)
print(c.value, c.stored)
c.value = 4
print(c.value, c.stored, isinstance(c, Base))
