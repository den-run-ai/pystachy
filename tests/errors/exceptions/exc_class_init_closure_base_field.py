# error: E.__init__ may leave field 'a' of Base unassigned where it is read: assign it, or call super().__init__(...) first
from typing import Callable


class Base(Exception):
    def __init__(self, m: str) -> None:
        super().__init__(m)
        self.a = 1


class E(Base):
    def __init__(self, code: int) -> None:
        f: Callable[[], int] = lambda: self.a
        super().__init__("x")
        print(f())
        self.code = code


try:
    raise E(2)
except E as e:
    print("caught", e.a, e.code, e)
