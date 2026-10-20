# error: exc_record_eq_narrow.py:23: error: comparing E objects (in a list, tuple, in, count, index, sort, min or max) calls __eq__() of F with a E, but it takes a F
# list == compares the NamedTuples' fields, which may be objects of F, whose __eq__ CPython
# calls with an E whatever its annotation says (CPython prints True)
from typing import NamedTuple


class E(Exception):
    pass


class F(E):
    def __eq__(self, other: "F") -> bool:
        return True


class NT(NamedTuple):
    err: E


xs = [NT(F("a"))]
ys = [NT(E("b"))]
print(xs)
print(xs == ys)
