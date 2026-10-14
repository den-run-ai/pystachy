# error: inheritance with generic class templates is not supported: annotate __init__ parameters
class Base:
    def __init__(self, n):
        self.n = n


class Child(Base):
    pass


print(Child(1).n)
