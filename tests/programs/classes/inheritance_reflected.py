# Both operands have the static base type: the runtime child reflected method must not be skipped.
class Base:
    def __add__(self, other: "Base") -> int:
        return 1


class Child(Base):
    def __radd__(self, other: Base) -> int:
        return 2


def add(a: Base, b: Base) -> int:
    return a + b


print(add(Base(), Child()))
