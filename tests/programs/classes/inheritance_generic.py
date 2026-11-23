# A class without an __init__ of its own derives from a class template (#962)
class Base:
    def __init__(self, n):
        self.n = n


class Child(Base):
    pass


print(Child(1).n)
