# error: exc_dc_in_narrow.py:23: error: comparing E objects (in a list, tuple, in, count, index, sort, min or max) calls __eq__() of F with a E, but it takes a F
# in compares the dataclass objects by the __eq__ @dataclass writes, which compares their
# fields, which may be objects of F, whose __eq__ CPython calls with an E (CPython prints True)
from dataclasses import dataclass


class E(Exception):
    pass


class F(E):
    def __eq__(self, other: "F") -> bool:
        return True


@dataclass
class Rec:
    err: E


rs = [Rec(F("a"))]
print(rs)
print(Rec(E("b")) in rs)
