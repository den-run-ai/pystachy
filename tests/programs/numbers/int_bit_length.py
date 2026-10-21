# int.bit_length() and int.bit_count() count the bits of the absolute value, as CPython's do:
# -2**63 has 64 bits, one of them set; a bool is the int it equals
import sys
from typing import TypeVar

T = TypeVar("T")


def bits(n: int | None) -> int:
    return n.bit_length()


def ones(x: T) -> int:
    return x.bit_count()


low = -sys.maxsize - 1
xs = [0, 1, -1, 2, 5, -5, 255, -256, 1023, 1024, 2**62, sys.maxsize, -sys.maxsize, low]
for x in xs:
    print(x, x.bit_length(), x.bit_count(), f"{x.bit_length():>3}")
print(all((1 << e).bit_length() == e + 1 and ((1 << e) - 1).bit_count() == e for e in range(63)))
print(sum(i.bit_count() for i in range(1000)), sum([(-i).bit_length() for i in range(1000)]))
b = len(sys.argv) > 1  # (True: the tests run with two arguments)
ob: bool | None = b
print(b.bit_length(), b.bit_count(), (not b).bit_length(), True.bit_count(), False.bit_length(), ob.bit_length())
print((5).bit_length(), (-5).bit_count(), (xs[4] * 3).bit_length(), abs(low + 1).bit_count(), len("hello").bit_count())
print(1 << xs[9].bit_length(), xs[-1].bit_length() - 1, ones(7), ones(True), ones(low))
print(bits(6))
try:
    print(bits(None))
except AttributeError as e:
    print("AttributeError:", e)
