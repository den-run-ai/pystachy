# error: enum class C's boundary= is supported as enum's STRICT, CONFORM or KEEP
# The compiler applies a flag class's boundary where it makes the class, by name (CPython's
# boundary may be any expression: printing C.A|2)
from enum import KEEP, Flag

chosen = KEEP


class C(Flag, boundary=chosen):
    A = 1


print(C(3))
