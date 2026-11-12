# pystachy: dynamic-any
from typing import Any


class Error(Exception):
    def __init__(self, value: int):
        print("initial", self.args)
        super().__init__(value, "detail")

    def replace(self, value: int) -> None:
        super().__init__(value)


number = int("1000")
original: Any = number
e = Error(number)
print(e.args, e.args[0] is original, e.args is e.args)
try:
    raise e
except Exception as caught:
    print(caught.args is e.args, caught.args)
    old = caught.args
    e.replace(2000)
    print(caught.args is e.args, caught.args, old)


class PlainError(ValueError):
    pass


plain = PlainError("plain", 4)
print(plain.args, repr(plain))
try:
    raise plain
except BaseException as error:
    print(error.args, error.args is plain.args)
