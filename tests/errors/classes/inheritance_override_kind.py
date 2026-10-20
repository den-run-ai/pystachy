# error: overriding 'make' of 'Base' with another kind of method (instance, static or class method) in 'Derived' is not supported
class Base:
    def __init__(self, n: int) -> None:
        self.n = n

    @staticmethod
    def make(n: int) -> int:
        return n


class Derived(Base):
    @classmethod
    def make(cls, n: int) -> int:
        return -n


print(Derived.make(3))
