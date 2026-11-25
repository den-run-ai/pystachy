# Missing attributes in a concrete factory constructor fail before method
# arguments run. The factory must not silently call the base's constructor.
def replacement() -> str:
    print("replacement")
    return "word"


class Base:
    def __init__(self, x):
        self.x = x

    @classmethod
    def make(cls, x: int):
        return cls(x)


class NeedText(Base):
    def __init__(self, x: str) -> None:
        super().__init__(x)
        self.converted: str = x.replace("x", replacement())


s = NeedText("x")
print(s.converted)
try:
    s.make(1)
    print("wrong")
except AttributeError as exc:
    print(type(exc).__name__, str(exc))
