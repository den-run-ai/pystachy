# Flag lookup checks the existing value map before asking _missing_() to create a member:
# equal floats can name declared members, or a composite already cached by an int lookup.
# Class containment checks declared values and only creates pseudo-members from ints; a float
# matching a cached composite is still not in the class unless that value was declared.
from enum import Flag, IntFlag

class F(Flag):
    A = 1
    B = 2
    ALL = 3
    NONE = 0

class G(Flag):
    A = 1
    B = 2

class I(IntFlag):
    A = 1
    B = 2
    ALL = 3

def check(cls):
    for value in [1.0, 3.0, 0.0, 4.0, -1.0, 1.5]:
        print(cls, value, value in cls)
        try:
            print(repr(cls(value)))
        except ValueError as e:
            print("ValueError", e)

check(F)
check(G)
print(repr(G(3)), repr(G(-1)))
check(G)
check(I)
print(repr(I(4)), repr(I(-1)))
check(I)
