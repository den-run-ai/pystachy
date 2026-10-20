# A def or lambda in an exception class's __init__ that reads only the class's own fields through
# self does not let self escape: the base's fields, which super().__init__() assigns later, keep
# no flag, and the closure's reads of the class's own fields test theirs.
from typing import Callable


class Base(Exception):
    def __init__(self, m: str) -> None:
        super().__init__(m)
        self.a = 1


class E(Base):
    def __init__(self, code: int) -> None:
        def describe() -> str:
            return "code " + str(self.code)

        self.code = code
        super().__init__(describe())


class F(Exception):
    def __init__(self, code: int) -> None:
        fmt: Callable[[], str] = lambda: "F" + str(self.code)
        self.code = code
        super().__init__(fmt())


class G(Base):
    def __init__(self, code: int) -> None:
        early: Callable[[], str] = lambda: "G" + str(self.code)
        try:
            print(early())
        except AttributeError as e:
            print("AttributeError:", e)
        self.code = code
        super().__init__(early())

        def later() -> int:
            return self.a + self.code

        self.total: int = later()


try:
    raise E(3)
except E as e:
    print("caught", e.a, e.code, e)
try:
    raise F(4)
except F as e:
    print("caught", e.code, e)
try:
    raise G(5)
except Base as e:
    print("caught", e.a, e, isinstance(e, G))
g = G(6)
print(g.total, g.code, g)
