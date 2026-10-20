class Base:
    def __init__(self, v: int) -> None:
        self.v = v


def f(x: Derived) -> int:
    return x.v


class Derived(Base):
    def same(self, o: Derived) -> bool:
        return True


def g() -> int:
    return 10
