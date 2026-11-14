# error: inheritance with generic class templates is not supported: annotate __init__ parameters with concrete types (not Any or object)
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


print(Child(3).value)
