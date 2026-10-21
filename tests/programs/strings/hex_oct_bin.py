# hex(), oct() and bin() of ints and bools: format()'s alternate form, with the sign in front;
# an int | None that is None raises CPython's TypeError
import sys


def maybe(n: int, none: bool) -> int | None:
    return None if none else n


class Reg:
    def __init__(self, n: int) -> None:
        self.h = hex(n)  # (a str field)
        self.o = oct(n)
        self.b = bin(n)


r = Reg(-42)
print(r.h, r.o, r.b, r.h.upper(), len(r.b))
for n in [0, 1, -1, 7, 8, 255, -255, 4096, -4096, 2 ** 31, sys.maxsize, -sys.maxsize, -sys.maxsize - 1]:
    print(n, hex(n), oct(n), bin(n))
print(hex(True), oct(True), bin(True), hex(False), oct(False), bin(False))
print(hex(-0), oct(-8), bin(0), hex(0x7F) == f"{0x7F:#x}", len(bin(-sys.maxsize - 1)))
t = True
print(hex(t), bin(not t), oct(t) + "!", [hex(k) for k in range(14, 18)])
print(int(hex(-sys.maxsize - 1), 16), int(oct(255), 8), int(bin(-5), 2), int(hex(123456), 0))
print(hex(maybe(255, False)), oct(maybe(-8, False)), bin(maybe(5, False)))
for name in ["hex", "oct", "bin"]:
    try:
        v = maybe(1, True)
        print(hex(v) if name == "hex" else oct(v) if name == "oct" else bin(v))
    except TypeError as e:
        print(name, "TypeError:", e)
