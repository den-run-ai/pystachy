# error: enum._test_simple_enum() is not supported: CPython's compares the two classes' __dict__s
# Importing the helper is supported, calling it is not (CPython prints ok)
import enum


class Checked(enum.Enum):
    A = 1


@enum._simple_enum(enum.Enum)
class Simple:
    A = 1


def check() -> None:
    enum._test_simple_enum(Checked, Simple)


check()
print("ok")
