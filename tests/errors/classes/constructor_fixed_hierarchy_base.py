# error: inheritance with generic class templates is not supported
class Base:
    def __init__(self, value):
        self.value: int = int(value)


class Child(Base):
    pass


print(Child(1).value)
