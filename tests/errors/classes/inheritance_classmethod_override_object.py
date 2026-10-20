# error: calling class method make() on an object of Base, which may be one of Derived, is not supported: Derived overrides it
class Base:
    def __init__(self, n: int) -> None:
        self.n = n

    @classmethod
    def make(cls, n: int) -> int:
        return n


class Derived(Base):
    @classmethod
    def make(cls, n: int) -> int:
        return -n


def use(b: Base) -> int:
    return b.make(3)


print(use(Derived(1)))
