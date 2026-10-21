# error: inheritance_reflected_override.py:17: error: reflected operator methods are not supported (Base + Child calls Child.__radd__)
# A child override has priority even when the base already defines the reflected operation.
class Base:
    def __add__(self, other: "Base") -> int:
        return 1

    def __radd__(self, other: "Base") -> int:
        return 3


class Child(Base):
    def __radd__(self, other: Base) -> int:
        return 2


def add(a: Base, b: Base) -> int:
    return a + b


print(add(Base(), Child()))
