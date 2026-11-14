# error: inheritance with generic class templates is not supported
class Base:
    pass


class Child(Base):
    def __init__(self, value):
        self.data = value
        self.next: Child | None = None


print(Child(1).data)
