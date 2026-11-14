# error: multiple inheritance requires an ordinary primary base and an independent method-only secondary base, or several
# A secondary base's property is a getter: a setter would store to the instance.
class Api:
    level: int

    @property
    def double(self) -> int:
        return self.level * 2

    @double.setter
    def double(self, v: int) -> None:
        self.level = v // 2


class Base:
    pass


class C(Base, Api):
    def __init__(self) -> None:
        self.level = 1
