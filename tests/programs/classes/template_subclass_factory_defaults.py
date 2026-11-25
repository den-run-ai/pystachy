def default() -> str:
    print("default")
    return "tail"


def value() -> int:
    print("value")
    return 5


class Base:
    def __init__(self, x):
        self.x = x

    @classmethod
    def make(cls, x: int):
        return cls(x=x)


class Sub(Base):
    def __init__(self, x: str, *, suffix: str = default()) -> None:
        super().__init__(x)
        self.suffix = suffix


b = Sub("a")
s = b.make(value())
print(type(s).__name__, s.x, s.suffix)
