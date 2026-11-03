# error: copy.copy() of a value of type A | B is not supported
# Only a value of one class (or of its subclasses) is copied (CPython prints A)
import copy


class A:
    def __init__(self) -> None:
        self.v = 1


class B:
    def __init__(self) -> None:
        self.w = 2


def pick(b: bool) -> A | B:
    return A() if b else B()


print(type(copy.copy(pick(True))).__name__)
