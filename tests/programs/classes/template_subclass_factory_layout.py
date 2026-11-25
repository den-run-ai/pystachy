# A cls factory infers a concrete subclass layout from the actual arguments.
# Class defaults retain their original storage and identity; only own instance
# fields widen, and existing objects retain their original field layouts (#1744).
def default() -> str:
    print("default")
    return "class"


class Base:
    count = 0

    def __init__(self, x):
        self.x = x

    @classmethod
    def make(cls, x: int):
        cls.count += 1
        return cls(x)


class Sub(Base):
    extra: str = default()

    def __init__(self, x: str) -> None:
        print("init", x, self.extra)
        super().__init__(x)
        self.extra = x + x
        self.annotated: str = x

    def see(self) -> None:
        print("Sub", self.x, self.extra, self.annotated)

    @classmethod
    def reset(cls, x: str) -> None:
        cls.extra = x


b = Sub("a")
s = b.make(1)
s.see()
print(type(s).__name__, isinstance(s, Sub), type(s) is Sub)
print(b.count, s.count, Base.count, Sub.count)
s.make(2).see()
Sub.reset("new")
print(b.count, s.count, Base.count, Sub.count)
print(b.extra, s.extra, Sub.extra)
