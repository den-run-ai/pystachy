# pystachy: python-int
# pack_into() evaluates its values before it converts the offset, as CPython does: past 64 bits,
# CPython's IndexError; a bool is the int it equals.
import struct


def v(x: int) -> int:
    print("value", x)
    return x


b = bytearray(4)
try:
    struct.pack_into("<BB", b, 2 ** 70, v(1), v(2))
except IndexError as e:
    print("IndexError:", e)
try:
    struct.pack_into("<BB", b, -(2 ** 70), v(3), v(4))
except IndexError as e:
    print("IndexError:", e)
struct.pack_into("<B", b, True, v(5))
big = 2 ** 70
struct.pack_into("<B", b, big - big + 2, v(6))
print(b)
