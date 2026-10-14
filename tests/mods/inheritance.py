class Base:
    def __init__(self, n: int) -> None:
        self.n = n

    def value(self) -> int:
        return self.n

    def twice(self) -> int:
        return self.value() * 2


class Derived(Base):
    def value(self) -> int:
        return super().value() + 10


class Owner:
    def __init__(self) -> None:
        self.child = Derived(3)

    def value(self) -> int:
        return self.child.twice()
