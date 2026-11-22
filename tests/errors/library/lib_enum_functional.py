# error: Enum() with members is supported as NAME = Enum('NAME', ...) at the top of a module, of literals: this one makes an enum class as the code runs
# CPython's functional API in a function makes a new enum class at each call (printing C.A); the
# compiler makes those of class statements and of such calls at the top of a module
from enum import Enum


def make() -> None:
    C = Enum("C", "A B")
    print(C.A)


make()
