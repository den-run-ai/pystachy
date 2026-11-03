# Enum classes of str and Enum and of int and Enum: members with str's and int's operations, as
# StrEnum's and IntEnum's have, but Enum's str() and format(), as CPython 3.12 gives a mixed-in enum
# class ("C.A", where a StrEnum member's str() is its value), and Enum's lookups
from enum import Enum


class C(str, Enum):
    A = "a"
    B = "b"


class N(int, Enum):
    ONE = 1
    TWO = 2


a = C.A
print(repr(a), str(a), f"{a}", format(a), a.value, a.name, a == a.value, hash(a) == hash(a.value))
o = N.ONE
print(repr(o), str(o), f"{o}", format(o), o.value, o.name, o == o.value, hash(o) == hash(o.value))
print(f"{N.ONE:>7}|{C.B:<4}|")
try:
    print(f"{N.ONE:d}")
except ValueError as e:
    print("ValueError", e)
print(C.A + "x", C.A.upper(), len(C.A), N.ONE + 1, N.TWO * 3, N.ONE < N.TWO, sorted([N.TWO, N.ONE]))
print(C("a"), N(2), list(C), C.__members__)
print(isinstance(C.A, Enum), isinstance(N.ONE, N), C.A in C, "b" in C, C.A == "a", "a" == C.A)
